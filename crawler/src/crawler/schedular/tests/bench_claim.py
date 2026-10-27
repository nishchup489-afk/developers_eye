"""Benchmark claim_targets(): single-worker latency and multi-worker drain.

Usage (from crawler/):
    poetry run python src/crawler/schedular/tests/bench_claim.py src/crawler/schedular/repository.py current

The first argument is the repository.py to measure, so an older copy can be
compared with the current one. Needs BENCH_DATABASE_URL: an asyncpg URL to a
migrated, throwaway database with "test" in its name. Other sources there are
disabled while it runs and re-enabled at the end.
"""
import asyncio
import importlib.util
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawler_frontier import CrawlTarget
from backend.models.source import Source


def load(path):
    spec = importlib.util.spec_from_file_location("repo_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.claim_targets


async def seed(factory, sources, per_source):
    tag = uuid4().hex[:8]
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with factory() as session, session.begin():
        ids = []
        for i in range(sources):
            ids.append(await session.scalar(insert(Source).values(
                slug=f"bench-{tag}-{i}", name="bench", kind="website",
                base_url="https://example.com/", allowed_hosts=["example.com"],
                crawl_interval_seconds=3600, is_enabled=True, config={},
            ).returning(Source.id)))
        rows = [
            dict(source_id=sid, fetch_url=f"https://example.com/{tag}/{sid}/{j}",
                 normalized_url=f"https://example.com/{tag}/{sid}/{j}",
                 priority=50, depth=j % 4, next_fetch_at=past)
            for sid in ids for j in range(per_source)
        ]
        for k in range(0, len(rows), 1000):
            await session.execute(insert(CrawlTarget), rows[k:k + 1000])
    return ids


async def cleanup(factory, ids):
    async with factory() as session, session.begin():
        await session.execute(delete(CrawlTarget).where(CrawlTarget.source_id.in_(ids)))
        await session.execute(delete(Source).where(Source.id.in_(ids)))


async def latency(factory, claim, runs=200, limit=10):
    times = []
    for _ in range(runs):
        async with factory() as session:
            await session.begin()
            start = time.perf_counter()
            got = await claim(session, limit=limit)
            await session.flush()
            times.append((time.perf_counter() - start) * 1000)
            await session.rollback()
            assert len(got) == limit
    times.sort()
    return statistics.median(times), times[int(len(times) * 0.95)]


async def drain(factory, claim, workers, limit=10):
    claimed, empty_while_work_left = [], [0]

    async def worker():
        while True:
            async with factory() as session, session.begin():
                got = await claim(session, limit=limit)
                claimed.extend(t.id for t in got)
            if got:
                continue
            async with factory() as session:
                left = await session.scalar(select(func.count()).select_from(CrawlTarget).where(
                    CrawlTarget.state == "queued", CrawlTarget.next_fetch_at <= func.now()))
            if not left:
                return
            empty_while_work_left[0] += 1

    start = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(workers)))
    elapsed = time.perf_counter() - start
    assert len(claimed) == len(set(claimed)), "duplicate claim"
    return len(claimed), elapsed, empty_while_work_left[0]


async def main(path, label):
    raw = os.environ["BENCH_DATABASE_URL"]
    if "test" not in (make_url(raw).database or "").lower():
        sys.exit('BENCH_DATABASE_URL must point at a database with "test" in its name')
    claim = load(path)
    engine = create_async_engine(raw, pool_size=20)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        paused = list(await session.scalars(
            update(Source).where(Source.is_enabled.is_(True)).values(is_enabled=False).returning(Source.id)))
    try:
        await run(factory, claim, label)
    finally:
        async with factory() as session, session.begin():
            if paused:
                await session.execute(update(Source).where(Source.id.in_(paused)).values(is_enabled=True))
        await engine.dispose()


async def run(factory, claim, label):
    for sources, per_source in ((1, 2000), (50, 40)):
        ids = await seed(factory, sources, per_source)
        p50, p95 = await latency(factory, claim)
        print(f"{label} | {sources} src x {per_source} | claim(limit=10) latency p50 {p50:.1f} ms p95 {p95:.1f} ms")
        await cleanup(factory, ids)
        for workers in (1, 4, 8):
            ids = await seed(factory, sources, per_source)
            n, elapsed, empty = await drain(factory, claim, workers)
            print(f"{label} | {sources} src x {per_source} | {workers} workers drain {n} targets in {elapsed:.2f} s "
                  f"({n / elapsed:.0f}/s), empty claims while work left: {empty}")
            await cleanup(factory, ids)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(sys.argv[1], sys.argv[2]), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main(sys.argv[1], sys.argv[2]))
