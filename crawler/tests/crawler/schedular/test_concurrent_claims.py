"""Concurrent claim_targets() regressions on committed rows (pytest).

Needs TEST_DATABASE_URL: a migrated, dedicated PostgreSQL database with "test"
in its name. Other sources in that database are disabled while a test runs and
re-enabled afterwards, so round robin only sees this test's sources.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawler_frontier import CrawlTarget
from backend.models.source import Source
from crawler.schedular.repository import claim_targets


@asynccontextmanager
async def database(source_count, targets_per_source):
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test database")
    url = make_url(raw)
    if url.drivername != "postgresql+asyncpg" or not url.database or "test" not in url.database.lower():
        pytest.fail("TEST_DATABASE_URL must be PostgreSQL+asyncpg with test in the database name")
    # lock_timeout turns a lock wait that never ends into a failure.
    engine = create_async_engine(raw, connect_args={
        "timeout": 5, "command_timeout": 15, "server_settings": {"lock_timeout": "5000"}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tag = uuid4().hex
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    source_ids, paused = [], []
    try:
        async with factory() as session, session.begin():
            paused = list(await session.scalars(
                update(Source).where(Source.is_enabled.is_(True)).values(is_enabled=False).returning(Source.id)))
            for i in range(source_count):
                source_ids.append(await session.scalar(insert(Source).values(
                    slug=f"concurrent-{tag}-{i}", name="Concurrent claim test", kind="website",
                    base_url="https://example.com/", allowed_hosts=["example.com"],
                    crawl_interval_seconds=3600, is_enabled=True, config={},
                ).returning(Source.id)))
            await session.execute(insert(CrawlTarget), [
                dict(source_id=sid, fetch_url=f"https://example.com/{tag}/{sid}/{j}",
                     normalized_url=f"https://example.com/{tag}/{sid}/{j}", next_fetch_at=past)
                for sid in source_ids for j in range(targets_per_source)])
        yield factory, source_ids
    finally:
        async with factory() as session, session.begin():
            if source_ids:
                await session.execute(delete(CrawlTarget).where(CrawlTarget.source_id.in_(source_ids)))
                await session.execute(delete(Source).where(Source.id.in_(source_ids)))
            if paused:
                await session.execute(update(Source).where(Source.id.in_(paused)).values(is_enabled=True))
        await engine.dispose()


async def overlapping_claims(factory, limit):
    """Claim in two transactions whose leases overlap: the first stays open
    while the second claims, then both commit."""
    first_session, second_session = factory(), factory()
    try:
        await first_session.begin()
        first = [(t.id, t.source_id) for t in await claim_targets(first_session, limit=limit)]

        async def second_claim():
            async with second_session.begin():
                return [(t.id, t.source_id) for t in await claim_targets(second_session, limit=limit)]

        second_task = asyncio.create_task(second_claim())
        # The second claim may wait on the source rows the first one updated.
        # It must not finish with fewer targets because of it.
        await asyncio.sleep(0.3)
        await first_session.commit()
        second = await asyncio.wait_for(second_task, timeout=10)
        return first, second
    finally:
        await first_session.close()
        await second_session.close()


async def drain(factory, workers, limit):
    claimed, empty_with_work_left = [], 0

    async def worker():
        nonlocal empty_with_work_left
        while True:
            async with factory() as session, session.begin():
                got = await claim_targets(session, limit=limit)
                claimed.extend(t.id for t in got)
            if got:
                continue
            # Only count rows nobody holds: a target locked by another
            # worker's open claim is about to become leased.
            async with factory() as session, session.begin():
                left = (await session.scalars(select(CrawlTarget.id).where(
                    CrawlTarget.state == "queued", CrawlTarget.next_fetch_at <= func.now(),
                ).with_for_update(skip_locked=True))).all()
            if not left:
                return
            empty_with_work_left += 1

    await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(workers))), timeout=60)
    return claimed, empty_with_work_left


def test_single_source_overlapping_claims_get_different_targets():
    async def run():
        async with database(1, 6) as (factory, (source_id,)):
            first, second = await overlapping_claims(factory, limit=3)
            assert len(first) == len(second) == 3
            assert {i for i, _ in first}.isdisjoint(i for i, _ in second)
            async with factory() as session:
                leased = await session.scalar(select(func.count()).select_from(CrawlTarget).where(
                    CrawlTarget.source_id == source_id, CrawlTarget.state == "leased"))
                assert leased == 6
                assert await session.scalar(select(Source.last_claimed_at).where(Source.id == source_id)) is not None
    asyncio.run(run())


def test_multi_source_overlapping_claims_stay_fair():
    async def run():
        async with database(2, 4) as (factory, (a, b)):
            first, second = await overlapping_claims(factory, limit=2)
            # Each worker takes one target from each source, none twice.
            assert sorted(s for _, s in first) == sorted(s for _, s in second) == [a, b]
            assert {i for i, _ in first}.isdisjoint(i for i, _ in second)
            async with factory() as session, session.begin():
                after = await claim_targets(session, limit=2)
                assert sorted(t.source_id for t in after) == [a, b]
    asyncio.run(run())


@pytest.mark.parametrize("sources,per_source", [(1, 60), (6, 10)])
def test_parallel_workers_drain_without_duplicates_or_idle_claims(sources, per_source):
    async def run():
        async with database(sources, per_source) as (factory, source_ids):
            claimed, empty_with_work_left = await drain(factory, workers=4, limit=5)
            assert len(claimed) == len(set(claimed)) == sources * per_source
            assert empty_with_work_left == 0
            async with factory() as session:
                stamps = (await session.scalars(select(Source.last_claimed_at).where(
                    Source.id.in_(source_ids)))).all()
                assert None not in stamps
    asyncio.run(run())
