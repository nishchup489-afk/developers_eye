"""A connection lost mid-transaction loses nothing and blocks nothing (PostgreSQL).

Needs TEST_DATABASE_URL: a migrated, dedicated database with "test" in its name.
"""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.session import DATABASE_UNAVAILABLE_ERRORS
from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawl_monitor import CrawlEvent
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.source import Source
from crawler.processing import ProcessedDocument
from crawler.scheduler.repository import recover_expired_leases
from crawler.worker.jobs import utility
from crawler.writer.attempts import start_attempt


@pytest_asyncio.fixture
async def db():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw or "test" not in (make_url(raw).database or ""):
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL database with test in its name")
    engine = create_async_engine(raw, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid4().hex
    lease = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=5)
    async with factory() as session, session.begin():
        source_id = await session.scalar(insert(Source).values(
            slug=f"fault-{tag}", name="Fault test", kind="website", base_url="https://example.com/",
            allowed_hosts=["example.com"], crawl_interval_seconds=3600, is_enabled=True, config={},
        ).returning(Source.id))
        url = f"https://example.com/{tag}"
        target_id = await session.scalar(insert(CrawlTarget).values(
            source_id=source_id, fetch_url=url, normalized_url=url, state="leased", lease_until=lease,
            next_fetch_at=datetime.now(timezone.utc),
        ).returning(CrawlTarget.id))
        attempt_id = await start_attempt(session, target_id, lease_until=lease)
    try:
        yield SimpleNamespace(engine=engine, factory=factory, source_id=source_id, target_id=target_id,
                              attempt_id=attempt_id, lease=lease, url=url, tag=tag)
    finally:
        async with factory() as session, session.begin():
            await session.execute(delete(Document).where(Document.source_id == source_id))
            await session.execute(delete(CrawlEvent).where(CrawlEvent.attempt_id == attempt_id))
            await session.execute(delete(CrawlAttempt).where(CrawlAttempt.crawl_target_id == target_id))
            await session.execute(delete(CrawlTarget).where(CrawlTarget.id == target_id))
            await session.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


def finalize_arguments(db):
    document = ProcessedDocument(
        url=db.url, canonical_url=db.url, document_type="article", title="Title", description=None,
        body="body text", author=None, content_hash=db.tag,
    )
    return dict(
        session_factory=db.factory, target_id=db.target_id, source_id=db.source_id,
        expected_lease_until=db.lease, attempt_id=db.attempt_id, action="complete", outcome="success",
        message="ok", http_status=200, body_bytes=9, retry_after_seconds=None, interval_seconds=3600,
        parsed=SimpleNamespace(discovered_links=()),
        processed=SimpleNamespace(documents=[document], skipped=[]),
        targets=[], elapsed=0.1,
    )


async def test_connection_lost_in_finalize_rolls_back_and_the_lease_recovers(db, monkeypatch):
    monkeypatch.setattr(utility, "_noindex_urls", lambda parsed, processed: set())
    real_finish = utility.finish_attempt

    async def finish_after_losing_connection(session, *args, **kwargs):
        pid = await session.scalar(select(func.pg_backend_pid()))
        async with db.factory() as admin, admin.begin():
            await admin.execute(select(func.pg_terminate_backend(pid)))
        return await real_finish(session, *args, **kwargs)

    monkeypatch.setattr(utility, "finish_attempt", finish_after_losing_connection)
    with pytest.raises(DATABASE_UNAVAILABLE_ERRORS):
        await utility._finalize(**finalize_arguments(db))

    async with db.factory() as session:
        target = await session.get(CrawlTarget, db.target_id)
        attempt = await session.get(CrawlAttempt, db.attempt_id)
        documents = await session.scalar(select(func.count(Document.id)).where(Document.source_id == db.source_id))
    assert (target.state, target.lease_until, target.failure_count) == ("leased", db.lease, 0)
    assert attempt.finished_at is None and attempt.outcome is None
    assert documents == 0, "the document write must roll back with the target transition"

    # The worker is gone. Once its lease expires the reaper puts the target back.
    async with db.factory() as session, session.begin():
        await session.execute(update(CrawlTarget).where(CrawlTarget.id == db.target_id).values(
            lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)))
    async with db.factory() as session, session.begin():
        await recover_expired_leases(session)
    async with db.factory() as session:
        target = await session.get(CrawlTarget, db.target_id)
        attempt = await session.get(CrawlAttempt, db.attempt_id)
    assert (target.state, target.lease_until, target.failure_count) == ("queued", None, 1)
    assert attempt.outcome == "failed" and attempt.finished_at is not None


async def test_pool_replaces_connections_killed_while_idle(db):
    async with db.factory() as session:
        pid = await session.scalar(select(func.pg_backend_pid()))
    async with db.factory() as session:
        assert await session.scalar(select(func.pg_backend_pid())) == pid, "the pool should reuse it"

    other = create_async_engine(db.engine.url)
    try:
        async with other.begin() as connection:
            await connection.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
    finally:
        await other.dispose()

    async with db.factory() as session:
        assert await session.scalar(select(func.pg_backend_pid())) != pid
