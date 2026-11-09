"""PostgreSQL integration tests for the corpus and search availability reports.

Same throwaway schema approach as test_system_reporting.py.

Requires TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test
    poetry run pytest tests/integration/test_search_reporting.py -v
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import backend.models  # noqa: F401  registers every table on Base.metadata
from backend.admin_services import corpus_reporting, search_reporting
from backend.admin_services.system_reporting import build_problems
from backend.api.search import _is_database_timeout
from backend.db.base import Base
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.search_minute import SearchMinute
from backend.models.source import Source
from backend.search.telemetry import LATENCY_BOUNDS_MS, SearchTelemetry

NOW = datetime.now(timezone.utc)
BUCKETS = len(LATENCY_BOUNDS_MS) + 1


@pytest_asyncio.fixture
async def session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or "test" not in (make_url(url).database or ""):
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL database whose name contains 'test'")
    engine = create_async_engine(url)
    schema = f"admin_test_{uuid4().hex[:8]}"
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


async def seed_corpus(session):
    docs = Source(slug="docs", name="Docs", kind="website", base_url="https://docs.example.com/",
                  allowed_hosts=["docs.example.com"], crawl_interval_seconds=60, is_enabled=True, config={})
    empty = Source(slug="empty", name="Empty", kind="website", base_url="https://empty.example.com/",
                   allowed_hosts=["empty.example.com"], crawl_interval_seconds=60, is_enabled=False, config={})
    session.add_all([docs, empty])
    await session.flush()
    for i, (host, age, available) in enumerate([("docs.example.com", 0, True), ("docs.example.com", 3, True),
                                                ("docs.example.com", 20, False), ("API.example.org", 90, True)]):
        document = Document(source_id=docs.id, canonical_url=f"https://{host}/{i}", document_type="documentation", title=f"Doc {i}",
                            body="x" * 100, content_hash=f"h{i}", metadata_={}, is_available=available,
                            last_seen_at=NOW - timedelta(days=age), updated_at=NOW)
        session.add(document)
        await session.flush()
        if available:
            session.add(SearchIndex(document_id=document.id, search_vector="", code_vector="", indexed_hash="v1:x", category="docs"))
    await session.flush()


async def test_corpus_report_counts_a_small_corpus_exactly(session):
    await seed_corpus(session)
    report = await corpus_reporting.build_corpus_report(session)

    assert report["estimates"]["exact"] is True
    s = report["summary"]
    assert (s["total_documents"], s["available_documents"], s["unavailable_documents"], s["indexed_documents"]) == (4, 3, 1, 3)
    assert s["indexed_percent"] == 100 and s["total_body_bytes"] == 400 and s["average_body_bytes"] == 100
    assert (s["sources"], s["enabled_sources"], s["hosts"]) == (2, 1, 2)
    assert report["sources"][0] | {"id": 0} == dict(id=0, slug="docs", name="Docs", enabled=True, documents=4, available=3,
                                                    share_percent=100, average_body_bytes=100)
    assert report["sources"][1]["documents"] == 0
    assert report["hosts"][0]["name"] == "docs.example.com" and report["hosts"][0]["documents"] == 3
    assert report["hosts"][1]["name"] == "api.example.org"
    assert [a["documents"] for a in report["freshness"]["seen"]] == [1, 1, 1, 1]
    assert report["freshness"]["indexed"][0]["documents"] == 3
    assert report["categories"][0]["name"] == "docs"
    assert {t["table"] for t in report["storage"]} >= {"document", "search_index"}


async def test_corpus_report_is_empty_safe(session):
    report = await corpus_reporting.build_corpus_report(session)
    assert report["summary"]["total_documents"] == 0
    assert report["summary"]["average_body_bytes"] is None
    assert report["summary"]["indexed_percent"] is None


async def test_corpus_report_scales_a_sample_of_a_large_table(session, monkeypatch):
    await seed_corpus(session)
    await session.execute(text("""
        INSERT INTO document (source_id, canonical_url, document_type, title, content_hash)
        SELECT (SELECT min(id) FROM source), 'https://bulk.example.com/' || g, 'documentation', 't', 'h'
        FROM generate_series(1, 20000) g"""))
    await session.execute(text("ANALYZE document"))
    monkeypatch.setattr(corpus_reporting, "EXACT_LIMIT", 1000)
    monkeypatch.setattr(corpus_reporting, "SAMPLE_ROWS", 5000)
    report = await corpus_reporting.build_corpus_report(session)

    assert report["estimates"]["exact"] is False
    assert report["estimates"]["sampled_documents"] < 19000
    assert report["summary"]["total_documents"] == pytest.approx(20004, rel=0.05)
    assert report["hosts"][0]["name"] == "bulk.example.com"


async def seed_minutes(session, *, hours=24):
    def row(age_minutes, process, **counts):
        buckets = [0] * BUCKETS
        buckets[3] = counts.get("successful", 0)
        return SearchMinute(minute=(NOW - timedelta(minutes=age_minutes)).replace(second=0, microsecond=0), process=process,
                            latency_sum_ms=counts.get("successful", 0) * 80, latency_buckets=buckets, **counts)
    session.add_all([row(2, "a", successful=90, timed_out=8, invalid=5), row(2, "b", successful=95, busy=2),
                     row(120, "a", successful=100), row(hours * 60 + 10, "a", successful=1000)])
    await session.flush()


async def test_search_report_merges_processes_and_excludes_invalid(session, monkeypatch):
    monkeypatch.setattr(search_reporting, "_expected_revision", lambda: None)
    await seed_minutes(session)
    report = await search_reporting.build_search_report(session, hours=24)

    t = report["totals"]
    assert (t["successful"], t["timed_out"], t["busy"], t["invalid"]) == (285, 8, 2, 5)
    assert t["answered"] == 295 and t["failed"] == 10 and t["requests"] == 300
    assert t["availability_percent"] == pytest.approx(96.61, abs=0.01)
    assert t["mean_ms"] == 80
    assert 50 < t["p50_ms"] <= 100 and 50 < t["p99_ms"] <= 100
    assert report["recent"]["answered"] == 195
    assert report["recording"] is True and report["partial"] is False
    assert len(report["timeline"]) == 60
    assert sum(s["requests"] for s in report["timeline"]) == 295
    assert sum(s["failed"] for s in report["timeline"]) == 10
    assert report["timeline"][-1]["requests"] == 195
    assert {p["process"] for p in report["processes"]} == {"a", "b"}
    assert report["status"] == "degraded"
    assert any("searches succeeded" in reason for reason in report["reasons"])


async def test_search_report_with_no_traffic_has_no_rates(session, monkeypatch):
    monkeypatch.setattr(search_reporting, "_expected_revision", lambda: None)
    monkeypatch.setattr(search_reporting, "corpus_snapshot_info", lambda: dict(documents=1, loaded_at=NOW))
    report = await search_reporting.build_search_report(session, hours=1)
    assert report["totals"]["availability_percent"] is None
    assert report["totals"]["p95_ms"] is None
    assert report["status"] == "ok" and report["reasons"] == []


async def test_search_report_flags_pending_migration_and_missing_table(session, monkeypatch):
    monkeypatch.setattr(search_reporting, "_expected_revision", lambda: "new")
    await session.execute(text("CREATE TABLE alembic_version (version_num text)"))
    await session.execute(text("INSERT INTO alembic_version VALUES ('old')"))
    await session.execute(text("DROP TABLE search_minute"))
    report = await search_reporting.build_search_report(session)

    assert report["recording"] is False
    assert report["schema"] == dict(current="old", expected="new", up_to_date=False)
    assert report["status"] == "degraded"
    assert any("alembic upgrade head" in reason for reason in report["reasons"])
    # The dashboard banner must also survive the missing table.
    assert (await build_problems(session))["version"] == 1


async def test_problems_report_search_failures(session):
    await seed_minutes(session)
    problems = await build_problems(session)
    assert [p["title"] for p in problems["problems"] if p["id"] == "search_failures"] == [
        "10 of 195 searches failed in the last 15 minutes"]


async def test_telemetry_flush_replaces_rather_than_adds(session):
    @asynccontextmanager
    async def factory():
        yield session

    telemetry = SearchTelemetry(process="test")
    telemetry.record("successful", 40)
    telemetry.record("timed_out")
    await telemetry.flush(factory)
    telemetry.record("successful", 40)
    await telemetry.flush(factory)
    await telemetry.flush(factory)

    rows = (await session.scalars(select(SearchMinute))).all()
    assert len(rows) == 1
    assert (rows[0].successful, rows[0].timed_out, rows[0].latency_sum_ms) == (2, 1, 80)
    assert rows[0].latency_buckets[2] == 2


async def test_statement_timeout_is_classified_as_a_timeout(session):
    await session.execute(text("SET LOCAL statement_timeout = 10"))
    with pytest.raises(Exception) as caught:
        await session.execute(text("SELECT pg_sleep(1)"))
    assert _is_database_timeout(caught.value)
