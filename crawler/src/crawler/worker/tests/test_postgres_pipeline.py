"""Dedicated PostgreSQL regression tests; never use the crawler's live database."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate, CrawlTargetRead
from backend.services.crawler_monitoring import build_monitor, inspect_document
from crawler.frontier.repository import enqueue_targets
from crawler.policy_and_politeness.policy_coordinator import FetchResult, PolicyCoordinator
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import RobotsDecision
from crawler.schedular.repository import claim_targets, recover_expired_leases
from crawler.worker.jobs.jobs import process_job
from crawler.worker.recovery import recover_failed_claim
from crawler.writer.attempts import start_attempt


@asynccontextmanager
async def database():
    raw = os.environ.get('TEST_DATABASE_URL')
    if not raw:
        pytest.skip('Set TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test database')
    url = make_url(raw)
    if url.drivername != 'postgresql+asyncpg' or not url.database or 'test' not in url.database.lower():
        pytest.fail('TEST_DATABASE_URL must be PostgreSQL+asyncpg with test in the database name')
    engine = create_async_engine(raw, connect_args={'timeout': 5, 'command_timeout': 15})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source_id = None
    try:
        async with factory() as session, session.begin():
            source = Source(slug='regression-' + uuid4().hex, name='Regression test', kind='website',
                base_url='https://example.com/docs', allowed_hosts=['example.com'],
                crawl_interval_seconds=60, is_enabled=True, config={'max_depth': 3, 'max_pages': 7})
            session.add(source)
            await session.flush()
            source_id = source.id
        yield factory, source_id
    finally:
        if source_id is not None:
            async with factory() as session, session.begin():
                ids = select(CrawlTarget.id).where(CrawlTarget.source_id == source_id)
                await session.execute(delete(Document).where(Document.source_id == source_id))
                await session.execute(delete(CrawlAttempt).where(CrawlAttempt.crawl_target_id.in_(ids)))
                await session.execute(delete(CrawlTarget).where(CrawlTarget.source_id == source_id))
                await session.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


async def seed(factory, source_id, count):
    async with factory() as session, session.begin():
        await enqueue_targets(session, [CrawlTargetCreate(source_id=source_id,
            fetch_url=f'https://example.com/docs/{i}', normalized_url=f'https://example.com/docs/{i}') for i in range(count)])


async def claim(factory, source_id, count=1):
    async with factory() as session, session.begin():
        targets = await claim_targets(session, limit=count, source_id=source_id)
        await asyncio.sleep(.01)
        return [CrawlTargetRead.model_validate(target) for target in targets]


def install_fetch(monkeypatch, statuses=None):
    statuses = iter(statuses) if statuses else None
    async def fetch(self, session, url):
        status = next(statuses) if statuses else 200
        html = f'<html><head><title>Python {url}</title></head><body><main>Useful Python documentation with code examples.</main><a href="/linked/a">A</a><a href="/linked/b">B</a><a href="/linked/c">C</a><a href="/linked/d">D</a></body></html>'
        return FetchResult(RobotsDecision.ALLOW, f'Fetched HTTP {status}', url, url,
            status_code=status, headers={'content-type': 'text/html'}, body=html.encode() if status == 200 else b'')
    monkeypatch.setattr(PolicyCoordinator, 'fetch', fetch)


def test_concurrent_claims_atomic_writes_and_shared_source_budget(monkeypatch):
    install_fetch(monkeypatch)
    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 4)
            first, second = await asyncio.gather(claim(factory, source_id, 2), claim(factory, source_id, 2))
            assert len(first) == len(second) == 2
            assert {t.id for t in first}.isdisjoint(t.id for t in second)
            manager = PolitenessManager(min_interval_seconds=0)
            results = await asyncio.gather(*(process_job(t, session_factory=factory, politeness_manager=manager) for t in first + second))
            assert all(r.outcome == 'success' for r in results)
            async with factory() as session:
                assert await session.scalar(select(func.count(CrawlTarget.id)).where(CrawlTarget.source_id == source_id)) == 7
                assert await session.scalar(select(func.count(Document.id)).where(Document.source_id == source_id)) == 4
                assert await session.scalar(select(func.count(CrawlAttempt.id)).join(CrawlTarget).where(
                    CrawlTarget.source_id == source_id, CrawlAttempt.finished_at.is_(None))) == 0
                monitor = await build_monitor(session, source_id=source_id)
                assert monitor['summary']['attempted'] == monitor['summary']['persisted'] == 4
                assert len(monitor['documents']) == 4
                detail = await inspect_document(session, monitor['documents'][0]['id'])
                assert detail['body'] and detail['is_available'] is True
    asyncio.run(run())


def test_removed_page_invalidates_index_and_recovers_when_restored(monkeypatch):
    install_fetch(monkeypatch, [200, 404, 200])
    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 1)
            manager = PolitenessManager(min_interval_seconds=0)
            target = (await claim(factory, source_id))[0]
            await process_job(target, session_factory=factory, politeness_manager=manager)
            async with factory() as session, session.begin():
                document = await session.scalar(select(Document).where(Document.source_id == source_id))
                session.add(SearchIndex(document_id=document.id, search_vector=func.to_tsvector('english', document.body), indexed_hash=document.content_hash))
            for status in [404, 200]:
                async with factory() as session, session.begin():
                    await session.execute(update(CrawlTarget).where(CrawlTarget.source_id == source_id,
                        CrawlTarget.id != target.id).values(next_fetch_at=func.now() + timedelta(days=1)))
                    await session.execute(update(CrawlTarget).where(CrawlTarget.id == target.id).values(next_fetch_at=func.now()))
                target = (await claim(factory, source_id))[0]
                await process_job(target, session_factory=factory, politeness_manager=manager)
                async with factory() as session:
                    document = await session.scalar(select(Document).where(Document.source_id == source_id))
                    assert document.is_available is (status == 200)
                    assert document.unavailable_http_status == (404 if status == 404 else None)
                    assert await session.scalar(select(func.count(SearchIndex.document_id)).where(SearchIndex.document_id == document.id)) == 0
    asyncio.run(run())


def test_expiration_and_old_worker_recovery_do_not_touch_new_claims():
    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 2)
            targets = await claim(factory, source_id, 2)
            old_lease = datetime.now(timezone.utc) - timedelta(seconds=10)
            async with factory() as session, session.begin():
                await session.execute(update(CrawlTarget).where(CrawlTarget.id == targets[0].id).values(lease_until=old_lease))
                expired = await start_attempt(session, targets[0].id, lease_until=old_lease)
                old = await start_attempt(session, targets[1].id, lease_until=old_lease)
                active = await start_attempt(session, targets[1].id, lease_until=targets[1].lease_until)
            await recover_failed_claim(factory, targets[1].id, old_lease, 'timeout', 'Old worker timed out')
            async with factory() as session, session.begin():
                assert await recover_expired_leases(session) == 1
            async with factory() as session:
                assert (await session.get(CrawlAttempt, expired)).outcome == 'failed'
                assert (await session.get(CrawlAttempt, old)).outcome == 'failed'
                assert (await session.get(CrawlAttempt, active)).finished_at is None
                recovered = await session.get(CrawlTarget, targets[0].id)
                assert recovered.failure_count == 1 and recovered.next_fetch_at > datetime.now(timezone.utc)
                assert (await session.get(CrawlTarget, targets[1].id)).lease_until == targets[1].lease_until
    asyncio.run(run())
