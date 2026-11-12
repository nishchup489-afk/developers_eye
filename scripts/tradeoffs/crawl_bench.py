"""Crawler trade-offs 6, 9 and 10, and the recrawl numbers for 15.

From the repository root with the crawler environment, on the benchmark copy:

  python scripts/tradeoffs/crawl_bench.py workers --workers 2 8 16 32 64 --seconds 45
  python scripts/tradeoffs/crawl_bench.py mixed   --workers 16 --users 10 --seconds 30
  python scripts/tradeoffs/crawl_bench.py pool    --pools 1:0 2:2 4:2 8:2 16:4 --tasks 25 --seconds 20
  python scripts/tradeoffs/crawl_bench.py recrawl

Nothing here contacts a real website. `workers` and `mixed` start
mock_hosts.py on 127.0.0.1:80 and crawl 64 fake hosts (h00.bench ... h63.bench)
through the real crawler: claim, robots, shared per-host politeness (2 s),
fetch, parse, process, write. Only the destination checks are bypassed, and only in
this process: DNS for *.bench answers 127.0.0.1, and the public-IP check accepts
127.0.0.1 (the crawler refuses private addresses by design).

`recrawl` is read only: it measures how many real pages changed between two
crawls in this database's crawl_attempt history and fits the change rate that
the guide uses to compare recrawl intervals.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HOSTS = [f"h{i:02d}.bench" for i in range(64)]
SLUG = "bench-mock-hosts"


def allow_local_mock_hosts() -> None:
    """Point *.bench at the mock server. Benchmark process only."""
    import crawler.fetcher.fetch as fetch
    import crawler.fetcher.transport as transport
    import crawler.policy_and_politeness.policy_coordinator as coordinator

    async def resolve(host: str) -> list[str]:
        if host.endswith(".bench"):
            return ["127.0.0.1"]
        raise coordinator.UnsafeDestinationError("benchmark: only *.bench hosts are allowed")

    def approved(ips):
        return tuple(ips)

    coordinator.resolve_safe_destination = resolve
    fetch.validate_approved_ips = approved
    transport.validate_approved_ips = approved


def start_mock(capacity: int, change_percent: int = 16) -> subprocess.Popen:
    import httpx
    proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name("mock_hosts.py")), "--port", "80",
                             "--capacity", str(capacity), "--change-percent", str(change_percent)])
    for _ in range(60):
        try:
            mock_stats(reset=True)
            return proc
        except httpx.HTTPError:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("mock server did not start on port 80")


def mock_stats(reset: bool = False) -> dict:
    import httpx
    path = "/__reset" if reset else "/__stats"
    return httpx.get(f"http://127.0.0.1:80{path}", headers={"host": "control.bench"}, timeout=5).json()


async def ensure_source() -> int:
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session, session.begin():
        source_id = await session.scalar(text("SELECT id FROM source WHERE slug = :s"), {"s": SLUG})
        if source_id is None:
            source_id = await session.scalar(text(
                "INSERT INTO source (slug, name, kind, base_url, allowed_hosts, crawl_interval_seconds, is_enabled, config) "
                "VALUES (:s, 'Benchmark mock hosts', 'website', 'http://h00.bench/', :hosts, 86400, true, "
                "CAST(:config AS jsonb)) RETURNING id"),
                {"s": SLUG, "hosts": HOSTS, "config": json.dumps(
                    {"max_depth": 0, "max_pages": 1_000_000, "discover_sitemaps": False, "allowed_path_prefixes": ["/"]})})
        # Hosts may be in backoff from an earlier run.
        await session.execute(text("DELETE FROM crawl_host WHERE host LIKE '%.bench'"))
    return int(source_id)


async def enqueue(source_id: int, label: str, per_host: int) -> None:
    from backend.db.session import SessionFactory
    from backend.schema.crawler_frontier import CrawlTargetCreate
    from crawler.frontier.repository import enqueue_targets
    targets = [CrawlTargetCreate(source_id=source_id, fetch_url=f"http://{h}/{label}/p{i}",
                                 normalized_url=f"http://{h}/{label}/p{i}", kind="page")
               for i in range(per_host) for h in HOSTS]
    async with SessionFactory() as session, session.begin():
        # The default per-call budget (DEFAULT_MAX_PAGES) would stop later runs.
        await enqueue_targets(session, targets, max_pages=1_000_000)


async def crawl_counts(source_id: int, label: str) -> dict:
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        rows = (await session.execute(text(
            "SELECT a.outcome, a.http_status, count(*) AS n, coalesce(sum(a.bytes_received), 0) AS b "
            "FROM crawl_attempt a JOIN crawl_target t ON t.id = a.crawl_target_id "
            "WHERE t.source_id = :s AND t.fetch_url LIKE :p GROUP BY 1, 2"),
            {"s": source_id, "p": f"%/{label}/%"})).all()
        docs = await session.scalar(text("SELECT count(*) FROM document WHERE canonical_url LIKE :p"),
                                    {"p": f"%/{label}/%"})
    return {"attempts": {f"{r.outcome}:{r.http_status}": r.n for r in rows},
            "bytes": sum(r.b for r in rows), "documents": docs}


async def park_leftovers(source_id: int) -> None:
    """Targets a run did not reach must not be claimed by the next run."""
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session, session.begin():
        # A cancelled run leaves leased targets, which would hold their hosts for
        # the whole lease and starve the next run, so release them too.
        await session.execute(text(
            "UPDATE crawl_target SET state = 'queued', lease_until = NULL, "
            "next_fetch_at = now() + interval '10 years' "
            "WHERE source_id = :s AND state IN ('queued', 'leased')"), {"s": source_id})


async def crawl_for(source_id: int, workers: int, seconds: float) -> None:
    from crawler.worker.runner import RunnerConfig, build_job_handler, run_continuous
    config = RunnerConfig(batch_size=workers, concurrency=workers, source_id=source_id, forever=True,
                          poll_seconds=0.5)
    task = asyncio.create_task(run_continuous(config=config, job_handler=build_job_handler()))
    await asyncio.sleep(seconds)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await park_leftovers(source_id)


async def bench_workers(args):
    allow_local_mock_hosts()
    source_id = await ensure_source()
    await park_leftovers(source_id)
    mock = start_mock(args.capacity)
    rows = []
    try:
        # Warm-up: fetch every host's robots.txt once so each run measures steady state.
        await enqueue(source_id, f"warm-{int(time.time())}", per_host=2)
        await crawl_for(source_id, 32, 20)
        for workers in args.workers:
            label = f"w{workers}-{int(time.time())}"
            await enqueue(source_id, label, per_host=max(10, int(args.seconds) + 5))
            mock_stats(reset=True)
            with common.ResourceSampler(extra_pids=[mock.pid]) as sampler:
                await crawl_for(source_id, workers, args.seconds)
            counts = await crawl_counts(source_id, label)
            server = mock_stats()
            rows.append({
                "workers": workers, "seconds": args.seconds, **counts,
                "docs_per_second": round(counts["documents"] / args.seconds, 2),
                "politeness_ceiling_docs_per_second": round(len(HOSTS) / 2.0, 1),
                "server": server, "resources": sampler.report(),
            })
            print(workers, rows[-1]["docs_per_second"], server, flush=True)
    finally:
        mock.terminate()
    common.write_report("06-crawler-concurrency", {
        "mock": f"{len(HOSTS)} hosts on 127.0.0.1:80, 40-250 ms per page, 429 under 1 s per host, 503 over {args.capacity} in flight",
        "politeness": "crawler default: 1 request in flight and 2 s between requests per host, shared through crawl_host",
        "pool_per_process": f"DB_POOL_SIZE={os.environ.get('DB_POOL_SIZE')} DB_MAX_OVERFLOW={os.environ.get('DB_MAX_OVERFLOW')}",
        "runs": rows}, args.output)


async def bench_mixed(args, url):
    """Search p95 alone, crawl alone, and both at once (trade-off 9)."""
    import http_bench
    allow_local_mock_hosts()
    source_id = await ensure_source()
    await park_leftovers(source_id)
    mock = start_mock(args.capacity)
    api = http_bench.start_server(url, {})
    await enqueue(source_id, f"warm-{int(time.time())}", per_host=2)
    await crawl_for(source_id, 32, 20)
    mix = http_bench.query_mix()
    out = {}
    try:
        await http_bench.load(4, 10, mix)  # warm
        with common.ResourceSampler(extra_pids=[api.pid, mock.pid]) as s:
            out["search_only"] = await http_bench.load(args.users, args.seconds, mix)
        out["search_only"]["resources"] = s.report()

        label = f"mixed-crawl-{int(time.time())}"
        await enqueue(source_id, label, per_host=int(args.seconds) + 5)
        with common.ResourceSampler(extra_pids=[api.pid, mock.pid]) as s:
            await crawl_for(source_id, args.workers, args.seconds)
        out["crawl_only"] = {**await crawl_counts(source_id, label), "resources": s.report()}

        label = f"mixed-both-{int(time.time())}"
        await enqueue(source_id, label, per_host=int(args.seconds) + 5)
        with common.ResourceSampler(extra_pids=[api.pid, mock.pid]) as s:
            search, _ = await asyncio.gather(http_bench.load(args.users, args.seconds, mix),
                                             crawl_for(source_id, args.workers, args.seconds))
        out["both"] = {"search": search, "crawl": await crawl_counts(source_id, label), "resources": s.report()}
    finally:
        http_bench.stop_server(api)
        mock.terminate()
    for key in ("crawl_only",):
        out[key]["docs_per_second"] = round(out[key]["documents"] / args.seconds, 2)
    out["both"]["crawl"]["docs_per_second"] = round(out["both"]["crawl"]["documents"] / args.seconds, 2)
    common.write_report("09-crawl-and-search", {"users": args.users, "crawler_workers": args.workers,
                                                "seconds": args.seconds, **out}, args.output)


async def bench_pool(args):
    """Search throughput and pool checkout waits per pool size (trade-off 10).

    Each size runs in a fresh child process because the engine reads the pool
    settings once at import.
    """
    rows = []
    for spec in args.pools:
        size, overflow = spec.split(":")
        proc = subprocess.run([sys.executable, __file__, "_pool_child", "--tasks", str(args.tasks),
                               "--seconds", str(args.seconds)],
                              env={**os.environ, "DB_POOL_SIZE": size, "DB_MAX_OVERFLOW": overflow,
                                   "DB_POOL_TIMEOUT_SECONDS": "5"}, capture_output=True, text=True)
        if proc.returncode:
            print(proc.stderr[-3000:])
            raise SystemExit(proc.returncode)
        row = json.loads(proc.stdout.strip().splitlines()[-1])
        row.update(pool_size=int(size), max_overflow=int(overflow))
        rows.append(row)
        print(spec, row["searches_per_second"], row["checkout_wait"].get("p95_ms"), row["errors"], flush=True)
    common.write_report("10-connection-pool", {
        "tasks": args.tasks, "seconds": args.seconds,
        "workload": "concurrent in-process search_documents() calls, one session each, mixed query set, warm DF cache",
        "max_connections_budget": {
            "postgres_max_connections": 100,
            "20_crawler_processes_at_2_plus_2": 80, "api_at_8_plus_2": 10, "indexer_at_4_plus_2": 6,
            "total_worst_case": 96},
        "runs": rows}, args.output)


async def pool_child(args):
    import random
    from sqlalchemy import text
    from backend.db.session import SessionFactory, engine
    from backend.search import service
    from backend.search.ranking.statistics import get_corpus_statistics
    import http_bench
    waits: list[float] = []
    pool_cls = type(engine.sync_engine.pool)
    original = pool_cls._do_get

    def timed(self):
        t0 = time.perf_counter()
        try:
            return original(self)
        finally:
            waits.append((time.perf_counter() - t0) * 1000)
    pool_cls._do_get = timed
    async with SessionFactory() as session:
        service.set_corpus_statistics(await get_corpus_statistics(session, "TEXT"),
                                      await get_corpus_statistics(session, "CODE"))
    mix = http_bench.query_mix()
    latencies, errors = [], {}
    stop_at = None

    async def worker(i):
        rng = random.Random(i)
        while time.perf_counter() < stop_at:
            item = rng.choice(mix)
            t0 = time.perf_counter()
            try:
                async with SessionFactory() as session:
                    await session.execute(text("SET LOCAL statement_timeout = '3s'"))
                    await service.search_documents(session, item["q"], mode=item["mode"], limit=20)
                latencies.append((time.perf_counter() - t0) * 1000)
            except Exception as exc:  # pool timeout, statement timeout
                errors[type(exc).__name__] = errors.get(type(exc).__name__, 0) + 1

    stop_at = time.perf_counter() + 5
    await asyncio.gather(*(worker(i) for i in range(args.tasks)))  # warm
    waits.clear(); latencies.clear(); errors.clear()
    with common.ResourceSampler() as sampler:
        stop_at = time.perf_counter() + args.seconds
        await asyncio.gather(*(worker(i) for i in range(args.tasks)))
    await engine.dispose()
    res = sampler.report()
    print(json.dumps({
        "searches_per_second": round(len(latencies) / res["wall_seconds"], 2),
        "latency": common.summarize(latencies), "checkout_wait": common.summarize(waits),
        "errors": errors, "resources": res}))


async def bench_recrawl(args):
    from sqlalchemy import text
    from backend.db.session import SessionFactory
    async with SessionFactory() as session:
        row = (await session.execute(text("""
            WITH two AS (
                SELECT crawl_target_id, min(started_at) AS t1, max(started_at) AS t2,
                       avg(bytes_received) AS bytes
                FROM crawl_attempt WHERE outcome = 'success'
                GROUP BY 1 HAVING count(*) = 2
            ), joined AS (
                SELECT two.*, d.updated_at >= two.t2 - interval '1 minute' AS changed
                FROM two
                JOIN crawl_target t ON t.id = two.crawl_target_id AND t.kind = 'page'
                JOIN document d ON d.canonical_url = t.normalized_url
            )
            SELECT count(*) AS pages, count(*) FILTER (WHERE changed) AS changed,
                   avg(extract(epoch FROM t2 - t1)) / 3600 AS hours, avg(bytes) AS bytes
            FROM joined"""))).one()
        sources = (await session.execute(text(
            "SELECT kind, crawl_interval_seconds, count(*) AS n FROM source WHERE is_enabled "
            "GROUP BY 1, 2 ORDER BY 3 DESC"))).all()
        avg_page = await session.scalar(text(
            "SELECT avg(bytes_received) FROM crawl_attempt WHERE outcome = 'success'"))
    pages, changed, hours, page_bytes = row.pages, row.changed, float(row.hours), float(row.bytes)
    p = changed / pages
    rate_per_hour = -math.log(1 - p) / hours  # Poisson change process fitted to one interval
    intervals = {"1 day": 24, "3 days": 72, "7 days": 168, "14 days": 336, "30 days": 720, "60 days": 1440}
    model = {}
    for name, h in intervals.items():
        x = rate_per_hour * h
        changed_share = 1 - math.exp(-x)
        stale = 1 - (changed_share / x)  # time-averaged share of pages whose stored copy is out of date
        per_100k = 100_000 * (720 / h)
        model[name] = {
            "fetches_per_100k_docs_per_month": round(per_100k),
            "gb_per_100k_docs_per_month": round(per_100k * page_bytes / 1e9, 1),
            "gb_per_2m_docs_per_month": round(20 * per_100k * page_bytes / 1e9, 1),
            "changed_page_yield": round(changed_share, 3),
            "useful_fetches_per_100k_per_month": round(per_100k * changed_share),
            "mean_stale_share": round(stale, 3),
        }
    common.write_report("15-recrawl-frequency", {
        "observed": {"recrawled_pages": pages, "changed": changed, "changed_share": round(p, 4),
                     "mean_hours_between_crawls": round(hours, 1), "mean_bytes_per_fetch": round(page_bytes),
                     "mean_bytes_all_successful_fetches": round(float(avg_page))},
        "fitted_change_rate_per_day": round(rate_per_hour * 24, 5),
        "mean_days_between_changes": round(1 / rate_per_hour / 24, 1),
        "assumption": "each page changes as an independent Poisson process with one shared rate; fitted to one observed interval",
        "source_intervals_configured": [dict(r._mapping) for r in sources],
        "model": model}, args.output)


async def main(args, url):
    from backend.db.session import engine
    try:
        if args.what == "workers":
            await bench_workers(args)
        elif args.what == "mixed":
            await bench_mixed(args, url)
        elif args.what == "pool":
            await bench_pool(args)
        elif args.what == "_pool_child":
            await pool_child(args)
        else:
            await bench_recrawl(args)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["workers", "mixed", "pool", "recrawl", "_pool_child"])
    parser.add_argument("--database-url")
    parser.add_argument("--workers", type=int, nargs="+", default=[2, 8, 16, 32, 64])
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument("--capacity", type=int, default=24)
    parser.add_argument("--pools", nargs="+", default=["1:0", "2:2", "4:2", "8:2", "16:4"])
    parser.add_argument("--tasks", type=int, default=25)
    parser.add_argument("--output", type=Path)
    a = parser.parse_args()
    if a.what == "mixed":
        a.workers = a.workers[0] if a.workers != [2, 8, 16, 32, 64] else 16
    os.environ.setdefault("CRAWLER_LOG_TO_FILE", "false")
    if a.what in ("workers", "mixed"):
        # One crawler process, as deploy/docker-compose.yml runs it (4 + 2 connections).
        pool = (4, 2)
    else:
        pool = (None, None)
    u = common.configure(a.database_url, pool_size=pool[0], max_overflow=pool[1])
    import logging
    logging.basicConfig(level=logging.WARNING)
    common.run(main(a, u))
