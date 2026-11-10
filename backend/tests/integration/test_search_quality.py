"""Admin search diagnostics and human relevance judging (ADR-0057).

Same throwaway-schema approach as test_search_reporting.py.
Requires TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import backend.models  # noqa: F401  registers every table on Base.metadata
from backend.admin_services import search_quality as quality
from backend.db.base import Base
from backend.models.search_quality import RelevanceJudgment, RelevanceRun, SearchSlowQuery
from backend.search.telemetry import SearchTelemetry

NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or "test" not in (make_url(url).database or ""):
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL database whose name contains 'test'")
    engine = create_async_engine(url)
    schema = f"quality_test_{uuid4().hex[:8]}"
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            await connection.run_sync(Base.metadata.create_all, checkfirst=False)
            yield AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            await transaction.rollback()
    finally:
        await engine.dispose()


def slow(query, ms, *, outcome="successful", minutes_ago=1, stages=None, stopped_in=None):
    return SearchSlowQuery(recorded_at=NOW - timedelta(minutes=minutes_ago), process="p1", query=query, mode="all",
                           page=1, outcome=outcome, elapsed_ms=ms, result_count=None if outcome != "successful" else 10,
                           stages=stages or {}, stopped_in=stopped_in)


@pytest.mark.asyncio
async def test_slow_report_groups_repeats_and_shows_where_timeouts_stopped(session, monkeypatch):
    session.add_all([
        slow("HTTP 500 internal server error", 10697, outcome="timed_out", stages={"retrieval": 40.0}, stopped_in="ranking"),
        slow("HTTP 500 internal server error", 2100, stages={"retrieval": 30.0, "ranking": 2000.0}),
        slow("python context manager", 1500, stages={"retrieval": 20.0, "ranking": 1400.0}),
        slow("old query", 9000, minutes_ago=60 * 30),
    ])
    await session.flush()
    memory = SearchTelemetry(process="p2")
    assert memory.record_slow(query="fast", mode="all", category=None, page=1, outcome="successful",
                              elapsed_ms=5, result_count=3, stages={}, stopped_in=None) is False
    assert memory.record_slow(query="pending one", mode="text", category="docs", page=2, outcome="successful",
                              elapsed_ms=4000, result_count=3, stages={"ranking": 3900.0}, stopped_in=None) is True
    monkeypatch.setattr(quality, "telemetry", memory)

    report = await quality.build_slow_query_report(session, hours=24)

    assert report["total"] == 4 and report["timed_out"] == 1
    assert report["queries"][0]["query"] == "pending one"           # unflushed rows show at once
    assert "old query" not in {row["query"] for row in report["queries"]}
    assert report["repeated"][0] == dict(query="HTTP 500 internal server error", mode="all", count=2,
                                         timed_out=1, max_ms=10697, mean_ms=6398)
    assert report["timeouts_by_stage"] == {"ranking": 1}
    assert report["stage_means_ms"]["ranking"] == pytest.approx((2000 + 1400 + 3900) / 3, abs=0.1)


@pytest.mark.asyncio
async def test_telemetry_flush_writes_slow_rows_once(session):
    memory = SearchTelemetry(process="p3")
    memory.record_slow(query="slow one", mode="all", category=None, page=1, outcome="timed_out",
                       elapsed_ms=4100, result_count=None, stages={"retrieval": 12.5}, stopped_in="ranking")

    class Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    session.begin = lambda: session.begin_nested()  # the fixture owns the outer transaction
    await memory.flush(factory=Factory())
    await memory.flush(factory=Factory())
    rows = (await session.scalars(select(SearchSlowQuery).where(SearchSlowQuery.process == "p3"))).all()
    assert [(r.query, r.outcome, r.stopped_in, r.stages) for r in rows] == [("slow one", "timed_out", "ranking", {"retrieval": 12.5})]
    assert memory.slow_rows() == []


DOCS = [  # BM25 order is the list order; PostgreSQL order is reversed.
    dict(url=f"https://docs.example.com/{i}", title=f"Page {i}", bm25_rank=i, postgres_rank=13 - i) for i in range(1, 13)
]


async def fake_capture(session, query, mode, *, source, text_corpus, code_corpus):
    return dict(candidate_count=len(DOCS), elapsed_ms=5, documents=DOCS)


@pytest.mark.asyncio
async def test_judging_workflow_scores_only_when_every_pooled_url_is_graded(session, monkeypatch):
    monkeypatch.setattr(quality, "capture_pool", fake_capture)
    await quality.upsert_query(session, dict(id="H001", query="python async api", mode="text", source="docs"))
    await session.flush()

    report = await quality.build_evaluation_report(session)
    assert report["queries"][0]["status"] == "not_pooled"

    pooled = await quality.capture_query_pool(session, "H001", text_corpus=None, code_corpus=None)
    assert pooled["pooled"] == 12            # union of both top-10 lists
    await session.flush()

    view = await quality.get_judging_query(session, "H001")
    assert [j["url"] for j in view["judgments"]] == sorted(d["url"] for d in DOCS)
    assert all("bm25_rank" not in j and "postgres_rank" not in j for j in view["judgments"])

    await quality.save_judgment(session, "H001", dict(url=DOCS[0]["url"], grade=3, note="ideal"), judge="nish")
    await session.flush()
    partial = (await quality.build_evaluation_report(session))["queries"][0]
    assert partial["status"] == "incomplete" and partial["graded"] == 1

    for doc in DOCS[1:]:
        await quality.save_judgment(session, "H001", dict(url=doc["url"], grade=0), judge="nish")
    await session.flush()
    report = await quality.build_evaluation_report(session, k=10)
    row = report["queries"][0]
    assert row["status"] == "complete"
    assert row["bm25"] == {"precision_at_10": 0.1, "mrr_at_10": 1.0, "ndcg_at_10": 1.0}
    assert row["postgresql"]["mrr_at_10"] == 0.0      # page 1 is 12th for PostgreSQL
    assert report["aggregate"]["complete_queries"] == 1

    # Re-pooling keeps grades and notes.
    await quality.capture_query_pool(session, "H001", text_corpus=None, code_corpus=None)
    await session.flush()
    kept = await session.get(RelevanceJudgment, ("H001", DOCS[0]["url"]))
    assert (kept.grade, kept.note, kept.judged_by) == (3, "ideal", "nish")
    assert len((await session.scalars(select(RelevanceRun))).all()) == 2


@pytest.mark.asyncio
async def test_judging_writes_are_validated(session):
    with pytest.raises(quality.JudgingError):
        await quality.upsert_query(session, dict(id="bad id!", query="x"))
    with pytest.raises(quality.JudgingError):
        await quality.upsert_query(session, dict(id="Q1", query="x", mode="fuzzy"))
    with pytest.raises(quality.JudgingError):
        await quality.upsert_query(session, dict(id="Q1", query="x", source="nowhere"))
    await quality.upsert_query(session, dict(id="Q1", query="x"))
    await session.flush()
    with pytest.raises(quality.JudgingError, match="not in the pool"):
        await quality.save_judgment(session, "Q1", dict(url="https://a.example/", grade=2), judge=None)
    with pytest.raises(quality.JudgingError):
        await quality.save_judgment(session, "Q1", dict(url="https://a.example/", grade=4, add=True), judge=None)
    with pytest.raises(quality.JudgingError):
        await quality.save_judgment(session, "Q1", dict(url="javascript:alert(1)", grade=1, add=True), judge=None)
    assert await quality.save_judgment(session, "missing", dict(url="https://a.example/", grade=1), judge=None) is None

    added = await quality.save_judgment(session, "Q1", dict(url="https://a.example/", grade=2, add=True), judge="nish")
    await session.flush()
    assert added["grade"] == 2
    assert (await session.get(RelevanceJudgment, ("Q1", "https://a.example/"))).origin == "added"
    assert await quality.remove_added_url(session, "Q1", "https://a.example/") is True
    assert await quality.delete_query(session, "Q1") is True
    assert await quality.delete_query(session, "Q1") is False


@pytest.mark.asyncio
async def test_import_human_set_is_idempotent_and_keeps_existing_queries(session, tmp_path):
    manifest = tmp_path / "queries.json"
    manifest.write_text(json.dumps({"queries": [
        dict(query_id="H001", query="python async api", mode="text", stratum="multi-term", source="docs"),
        dict(query_id="H002", query="HTTP 404", mode="code", stratum="error-message", source=None),
    ]}), encoding="utf-8")
    await quality.upsert_query(session, dict(id="H001", query="edited by the judge", mode="all"))
    await session.flush()
    assert await quality.import_human_set(session, manifest) == {"added": 1, "total": 2}
    await session.flush()
    assert await quality.import_human_set(session, manifest) == {"added": 0, "total": 2}
    view = await quality.get_judging_query(session, "H001")
    assert view["query"] == "edited by the judge"


def test_shipped_human_set_is_well_formed():
    data = json.loads(quality.HUMAN_SET.read_text(encoding="utf-8"))
    ids = [q["query_id"] for q in data["queries"]]
    assert len(ids) == len(set(ids)) >= 30
    assert all(q["mode"] in quality.MODES for q in data["queries"])
