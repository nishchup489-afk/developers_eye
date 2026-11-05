"""PostgreSQL integration tests for admin capacity, host and problem reporting.

Each test builds the full schema inside a throwaway schema in one transaction
and rolls it back, so no real rows are touched.

Requires TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test
(the database needs `CREATE EXTENSION pg_trgm`).
    poetry run pytest tests/integration/test_system_reporting.py -v
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import backend.models  # noqa: F401  registers every table on Base.metadata
from backend.admin_services import system_reporting as reporting
from backend.admin_services.maintenance import purge_events
from backend.db.base import Base
from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawl_monitor import CrawlEvent, CrawlWorker, IndexerWorker
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.source import Source

NOW = datetime.now(timezone.utc)


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


async def seed(session, *, throttle=False):
    source = Source(slug="docs", name="Docs", kind="website", base_url="https://docs.example.com/",
                    allowed_hosts=["docs.example.com"], crawl_interval_seconds=60, is_enabled=True, config={})
    session.add(source)
    await session.flush()
    targets = []
    for i, host in enumerate(["docs.example.com"] * 8 + ["api.example.org"] * 2):
        target = CrawlTarget(source_id=source.id, fetch_url=f"https://{host}/page/{i}?q=1", normalized_url=f"https://{host}/page/{i}",
                             state="queued", next_fetch_at=NOW - timedelta(minutes=1))
        session.add(target)
        targets.append(target)
    await session.flush()
    for i, target in enumerate(targets):
        status = 429 if throttle and i < 3 else 200
        attempt = CrawlAttempt(crawl_target_id=target.id, started_at=NOW - timedelta(minutes=2), finished_at=NOW - timedelta(minutes=1),
                               http_status=status, outcome="failed" if status == 429 else "success", bytes_received=1000,
                               telemetry={"fetch_ms": 120, "stored": 0 if status == 429 else 1, "fetch_success": status == 200})
        session.add(attempt)
        await session.flush()
        session.add(CrawlEvent(attempt_id=attempt.id, stage="DEDUP", outcome="new", details={}))
        if i == 0:
            session.add(CrawlEvent(attempt_id=attempt.id, stage="FETCH", outcome="success", details={},
                                   created_at=NOW - timedelta(days=40)))
    for i in range(4):
        session.add(Document(source_id=source.id, canonical_url=f"https://docs.example.com/d/{i}", document_type="documentation",
                             title=f"Doc {i}", body="x" * 500, content_hash="same" if i < 2 else f"h{i}", metadata_={},
                             last_seen_at=NOW, updated_at=NOW))
    await session.flush()
    return source


async def test_system_report_budget_progress_and_yield(session, monkeypatch):
    monkeypatch.setattr(reporting.settings, "admin_target_documents", 100)
    monkeypatch.setattr(reporting.settings, "admin_db_budget_gb", 120.0)
    await seed(session)
    report = await reporting.build_system_report(session, days=7)

    assert report["version"] == 1
    budget = report["budget"]
    assert budget["used_bytes"] == report["database"]["size_bytes"] > 0
    assert budget["bytes_per_document"] == pytest.approx(budget["used_bytes"] / 4, rel=1e-3)
    assert budget["target_bytes_per_document"] == pytest.approx(120 * 1024 ** 3 / 100)
    assert budget["documents_that_fit"] > 0
    names = {t["name"] for t in report["tables"]}
    assert {"document", "crawl_attempt", "crawl_event", "indexer_worker"} <= names
    progress = report["progress"]
    assert progress["documents"] == 4 and progress["remaining"] == 96
    assert progress["new_last_24h"] == 10 and progress["eta_days"] == pytest.approx(9.6)
    [docs] = report["sources"]
    assert docs["attempts"] == 10 and docs["stored_attempts"] == 10 and docs["yield_percent"] == 100
    assert docs["documents"] == 4 and docs["duplicate_documents"] == 1
    assert report["telemetry"]["events_past_retention"] == 1


def test_budget_status_thresholds():
    gb = reporting.GB
    assert reporting._budget(10 * gb, 1000, budget_gb=100, target=1000)["status"] == "ok"
    assert reporting._budget(85 * gb, 1000, budget_gb=100, target=1000)["status"] == "warning"
    assert reporting._budget(96 * gb, 1000, budget_gb=100, target=1000)["status"] == "critical"
    # Fine today, but the projection to the goal overflows the budget.
    projected = reporting._budget(10 * gb, 100, budget_gb=100, target=5000)
    assert projected["status"] == "warning" and projected["projected_percent_of_budget"] == 500
    assert reporting._budget(0, 0, budget_gb=100, target=10)["bytes_per_document"] is None


async def test_host_report_rates_and_flags(session, monkeypatch):
    monkeypatch.setattr(reporting.settings, "admin_host_min_interval_seconds", 30.0)
    await seed(session, throttle=True)
    session.add(CrawlWorker(id="w1", hostname="pc", pid=1, started_at=NOW, heartbeat_at=NOW, last_active_at=NOW,
                            concurrency=4, batch_size=4, active_targets=[]))
    await session.flush()
    report = await reporting.build_host_report(session, minutes=60)

    assert report["total_attempts"] == 10 and report["online_workers"] == 1
    assert report["polite_requests_per_minute"] == 2.0 and report["worst_case_requests_per_minute"] == 2.0
    first, second = report["hosts"]
    assert first["host"] == "docs.example.com" and first["attempts"] == 8 and first["share_percent"] == 80
    assert first["http_429"] == 3 and first["requests_per_minute"] == 1.6
    assert set(first["flags"]) == {"throttled", "hot"}
    assert second["host"] == "api.example.org" and second["flags"] == []


async def test_problems_detect_stale_workers_throttling_and_retention(session, monkeypatch):
    monkeypatch.setattr(reporting.settings, "admin_target_documents", 5_000_000)
    monkeypatch.setattr(reporting.settings, "admin_db_budget_gb", 0.001)  # ~1 MB: the test DB is over budget
    await seed(session, throttle=True)
    old = NOW - timedelta(minutes=10)
    session.add(CrawlWorker(id="crashed", hostname="pc", pid=7, started_at=old, heartbeat_at=old, last_active_at=old,
                            concurrency=1, batch_size=1, active_targets=[]))
    session.add(IndexerWorker(id="ix", hostname="pc", pid=8, started_at=old, heartbeat_at=old, concurrency=1, batch_size=1))
    await session.flush()
    report = await reporting.build_problems(session)
    ids = {p["id"] for p in report["problems"]}

    assert {"crawler_heartbeat_stale", "crawler_offline", "indexer_heartbeat_stale", "indexer_behind",
            "disk_budget_critical", "disk_projection_over", "hosts_throttling", "telemetry_retention"} <= ids
    assert report["problems"][0]["severity"] == "critical"
    assert report["counts"]["critical"] >= 1


async def test_problems_quiet_on_healthy_system(session, monkeypatch):
    monkeypatch.setattr(reporting.settings, "admin_target_documents", 4)
    monkeypatch.setattr(reporting.settings, "admin_db_budget_gb", 1000.0)
    await seed(session)
    session.add(CrawlWorker(id="w", hostname="pc", pid=1, started_at=NOW, heartbeat_at=NOW, last_active_at=NOW,
                            concurrency=1, batch_size=1, active_targets=[]))
    for document_id in (await session.scalars(text("SELECT id FROM document"))).all():
        session.add(SearchIndex(document_id=document_id, search_vector="", code_vector="", indexed_hash="v1:x", indexed_at=NOW))
    await session.execute(text("DELETE FROM crawl_event WHERE created_at < now() - interval '1 day'"))
    await session.flush()
    report = await reporting.build_problems(session)
    assert report["problems"] == []


async def test_purge_events_deletes_only_old_rows(session):
    await seed(session)
    await session.flush()

    class Nested:
        """The fixture already holds the outer transaction; purge's begin() becomes a savepoint."""
        def __getattr__(self, name):
            return getattr(session, name)

        def begin(self):
            return session.begin_nested()

    class Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return Nested()

        async def __aexit__(self, *args):
            return False

    assert await purge_events(Factory(), days=14, dry_run=True) == 1
    assert await purge_events(Factory(), days=14, batch=1) == 1
    assert await session.scalar(text("SELECT count(*) FROM crawl_event")) == 10


async def test_indexer_report_lists_heartbeats(session):
    from backend.admin_services.indexer_reporting import build_indexer_report
    await seed(session)
    session.add(IndexerWorker(id="live", hostname="pc", pid=3, started_at=NOW, heartbeat_at=NOW, concurrency=2, batch_size=100,
                              indexed_total=40, failed_total=1))
    session.add(IndexerWorker(id="gone", hostname="pc", pid=4, started_at=NOW, heartbeat_at=NOW - timedelta(minutes=5),
                              stopped_at=NOW - timedelta(minutes=5), concurrency=2, batch_size=100))
    await session.flush()
    report = await build_indexer_report(session)
    assert report["activity"]["online_workers"] == 1
    assert {w["id"]: w["status"] for w in report["workers"]} == {"live": "online", "gone": "stopped"}
