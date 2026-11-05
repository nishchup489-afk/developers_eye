"""Cross-process politeness on real PostgreSQL. Needs TEST_DATABASE_URL."""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawl_host import CrawlHost
from crawler.policy_and_politeness.shared_politeness import HostBusyError, SharedPolitenessManager


@asynccontextmanager
async def manager_for_host(**limits):
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test database")
    if "test" not in (make_url(raw).database or "").lower():
        pytest.fail("TEST_DATABASE_URL must point at a test database")
    engine = create_async_engine(raw)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    host = f"{uuid4().hex}.example.com"
    limits = {"min_interval_seconds": 0.2, "hold_seconds": 5.0, "max_wait_seconds": 5.0, **limits}
    try:
        yield SharedPolitenessManager(factory, **limits), SharedPolitenessManager(factory, **limits), host, factory
    finally:
        async with factory() as session, session.begin():
            await session.execute(delete(CrawlHost).where(CrawlHost.host == host))
        await engine.dispose()


async def timed_requests(manager, url, spans, count):
    for _ in range(count):
        async with manager.polite_slot(url):
            started = time.monotonic()
            await asyncio.sleep(0.03)
            spans.append((started, time.monotonic()))


async def test_two_managers_share_one_gap_and_never_overlap():
    async with manager_for_host() as (first, second, host, _):
        url = f"https://{host}/page"
        spans = []
        await asyncio.gather(timed_requests(first, url, spans, 3), timed_requests(second, url, spans, 3))
        spans.sort()
        assert len(spans) == 6
        for earlier, later in zip(spans, spans[1:]):
            assert later[0] >= earlier[1], "requests overlapped"
            assert later[0] - earlier[1] >= 0.15, "gap not honored across managers"


async def test_backoff_from_one_manager_stops_the_other():
    async with manager_for_host(max_wait_seconds=0.2) as (first, second, host, _):
        url = f"https://{host}/page"
        await first.record_response(url, 429, "120")
        with pytest.raises(HostBusyError):
            async with second.polite_slot(url):
                pytest.fail("request started during another worker's backoff")


async def test_shorter_backoff_never_replaces_a_longer_one():
    async with manager_for_host() as (first, second, host, factory):
        url = f"https://{host}/page"
        await first.apply_backoff(url, 100)
        await second.apply_backoff(url, 1)
        async with factory() as session:
            left = await session.scalar(select(CrawlHost.backoff_until - func.clock_timestamp()).where(CrawlHost.host == host))
        assert left.total_seconds() > 90


async def test_crashed_holder_blocks_only_until_its_hold_expires():
    async with manager_for_host(hold_seconds=0.3) as (crashed, other, host, _):
        url = f"https://{host}/page"
        await crashed.acquire(url)  # never released
        started = time.monotonic()
        async with other.polite_slot(url):
            pass
        assert 0.2 <= time.monotonic() - started < 2


async def test_prepaid_first_request_skips_the_gate_once():
    async with manager_for_host(max_wait_seconds=0.1) as (manager, _, host, factory):
        url = f"https://{host}/page"
        await manager.acquire(url)  # stands in for the claim's hold
        manager.prepay(host)
        async with manager.polite_slot(url):
            pass
        async with factory() as session, session.begin():
            await session.execute(update(CrawlHost).where(CrawlHost.host == host).values(
                next_allowed_at=func.now() + func.make_interval(0, 0, 0, 0, 0, 0, 60)))
        with pytest.raises(HostBusyError):
            await manager.acquire(url)


async def test_settle_frees_an_unused_prepaid_hold():
    async with manager_for_host(min_interval_seconds=0) as (manager, other, host, _):
        url = f"https://{host}/page"
        await manager.acquire(url)
        manager.prepay(host)
        await manager.settle()
        async with other.polite_slot(url):
            pass
