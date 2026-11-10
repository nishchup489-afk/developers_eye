"""Crawl load test against a fake web. Sends nothing to the network.

Runs real crawler worker processes (claim, policy, parse, process, finalize)
against PostgreSQL, with DNS and HTTP replaced by an in-process fake. Every fake
request start and end is logged, then merged across processes to measure the
true aggregate rate and every per-host politeness violation.

Usage (from crawler/):
    BENCH_DATABASE_URL=postgresql+asyncpg://.../name_with_test \
    python tests/benchmarks/fake_web_load.py --workers 4 --concurrency 20 \
        --hosts 20 --pages 300 --gap 0.5 --latency-ms 80 --seconds 30

The database must be migrated, disposable, and have "test" in its name. Only
rows of sources named fakeweb-* are created and removed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import selectors
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit
from bench_safety import benchmark_database_url

WORDS = ("async await python rust kernel socket buffer thread module package index query "
         "vector cache schema lexer parser token stream router client server deploy").split()


def page_html(url: str) -> bytes:
    rng = random.Random(url)
    body = " ".join(rng.choices(WORDS, k=400))
    return (f"<html lang=en><head><title>{url}</title></head><body><main><h1>{url}</h1>"
            f"<p>{body}</p></main></body></html>").encode()


class FakeFetcher:
    """One-hop fetcher that logs when each request really starts and ends."""

    def __init__(self, log_path: str, latency: float, throttle_every: int) -> None:
        self.log = open(f"{log_path}.{os.getpid()}", "w", buffering=1, encoding="utf8")
        self.latency = latency
        self.throttle_every = throttle_every
        self.count = 0

    async def fetch_once(self, *, url, approved_ips, max_body_bytes, timeout_seconds, user_agent):
        from crawler.fetcher.schemas import OneHopResponse

        started = time.time()
        await asyncio.sleep(self.latency * random.uniform(0.5, 1.5))
        path = urlsplit(url).path
        self.count += 1
        if self.throttle_every and self.count % self.throttle_every == 0:
            response = OneHopResponse(429, {"retry-after": "3"}, b"")
        elif path == "/robots.txt":
            response = OneHopResponse(200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /\n")
        else:
            response = OneHopResponse(200, {"content-type": "text/html"}, page_html(url))
        self.log.write(json.dumps({"host": urlsplit(url).hostname, "start": started, "end": time.time(),
                                   "status": response.status_code}) + "\n")
        return response


async def seed(args) -> None:
    from sqlalchemy import delete, select, update
    from backend.db.session import SessionFactory, engine
    from backend.models import Document
    from backend.models.crawl_attempt import CrawlAttempt
    from backend.models.crawl_monitor import CrawlEvent
    from backend.models.crawler_frontier import CrawlTarget
    from backend.models.source import Source
    from backend.schema.crawler_frontier import CrawlTargetCreate
    from crawler.frontier.repository import enqueue_targets

    async with SessionFactory() as session, session.begin():
        old = select(Source.id).where(Source.slug.like("fakeweb-%"))
        targets = select(CrawlTarget.id).where(CrawlTarget.source_id.in_(old))
        attempts = select(CrawlAttempt.id).where(CrawlAttempt.crawl_target_id.in_(targets))
        await session.execute(delete(CrawlEvent).where(CrawlEvent.attempt_id.in_(attempts)))
        await session.execute(delete(Document).where(Document.source_id.in_(old)))
        await session.execute(delete(CrawlAttempt).where(CrawlAttempt.id.in_(attempts)))
        await session.execute(delete(CrawlTarget).where(CrawlTarget.id.in_(targets)))
        await session.execute(delete(Source).where(Source.id.in_(old)))
        await session.execute(update(Source).values(is_enabled=False))

    for number in range(args.hosts):
        host = f"h{number}.fakeweb.example"
        async with SessionFactory() as session, session.begin():
            source = Source(slug=f"fakeweb-{number}", name=host, kind="website",
                            base_url=f"https://{host}/", allowed_hosts=[host],
                            crawl_interval_seconds=86_400, is_enabled=True,
                            config={"max_depth": 3, "max_pages": args.pages * 2,
                                    "discover_sitemaps": False})
            session.add(source)
            await session.flush()
            urls = [f"https://{host}/p/{i}" for i in range(args.pages)]
            await enqueue_targets(session, [
                CrawlTargetCreate(source_id=source.id, fetch_url=url, normalized_url=url)
                for url in urls
            ], max_pages=args.pages * 2)
    await engine.dispose()


async def worker(args) -> int:
    import crawler.policy_and_politeness.policy_coordinator as coordinator
    from crawler.worker import runner

    async def fake_dns(self, url):
        return ["93.184.216.34"]

    coordinator.PolicyCoordinator._approved_ips = fake_dns
    fetcher = FakeFetcher(args.log, args.latency_ms / 1000, args.throttle_every)
    config = runner.RunnerConfig(batch_size=args.concurrency, concurrency=args.concurrency,
                                 forever=True, poll_seconds=0.2)
    if hasattr(runner, "build_job_handler"):
        handler = runner.build_job_handler(min_interval_seconds=args.gap, fetcher=fetcher)
    else:  # baseline: the in-process limiter
        from crawler.policy_and_politeness.politeness_policy import PolitenessManager
        manager = PolitenessManager(max_concurrent_per_host=1, min_interval_seconds=args.gap)
        handler = partial(runner.load_job_handler(), politeness_manager=manager, fetcher=fetcher)
    try:
        await asyncio.wait_for(runner.run_worker(config=config, job_handler=handler), args.seconds)
    except TimeoutError:
        pass
    finally:
        from backend.db.session import engine
        await engine.dispose()
        fetcher.log.close()
    return 0


def summarize(log_path: str, args, seconds: float) -> dict:
    rows = [json.loads(line) for path in Path(log_path).parent.glob(Path(log_path).name + ".*")
            for line in path.read_text(encoding="utf8").splitlines() if line.endswith("}")]
    by_host = defaultdict(list)
    for row in rows:
        by_host[row["host"]].append(row)
    gap_violations = overlaps = 0
    tolerance = min(0.005, args.gap * 0.05)
    for host_rows in by_host.values():
        host_rows.sort(key=lambda row: row["start"])
        for earlier, later in zip(host_rows, host_rows[1:]):
            if later["start"] - earlier["start"] < args.gap - tolerance:
                gap_violations += 1
            if later["start"] < earlier["end"]:
                overlaps += 1
    starts = sorted(row["start"] for row in rows)
    active = (starts[-1] - starts[0]) if len(starts) > 1 else 0.0
    return {
        "workers": args.workers, "concurrency": args.concurrency, "hosts": args.hosts,
        "gap_seconds": args.gap, "latency_ms": args.latency_ms, "run_seconds": round(seconds, 1),
        "requests": len(rows), "requests_per_second": round(len(rows) / active, 2) if active else 0,
        "ideal_requests_per_second": round(args.hosts / args.gap, 2),
        "gap_violations": gap_violations, "overlapping_requests": overlaps,
        "comparison_tolerance_seconds": tolerance,
        "throttled_429": sum(row["status"] == 429 for row in rows),
        "median_requests_per_host": statistics.median(len(v) for v in by_host.values()) if by_host else 0,
    }


async def database_snapshot():
    from sqlalchemy import text
    from backend.db.session import SessionFactory, engine
    try:
        async with SessionFactory() as session:
            stats = (await session.execute(text("SELECT xact_commit, xact_rollback, tup_inserted, tup_updated FROM pg_stat_database WHERE datname=current_database()"))).mappings().one()
            summary = (await session.execute(text("SELECT count(*) AS attempts, count(*) FILTER (WHERE finished_at IS NOT NULL) AS finished FROM crawl_attempt"))).mappings().one()
            tables = (await session.execute(text("SELECT relname,n_tup_upd,n_tup_hot_upd,n_dead_tup,pg_total_relation_size(relid) AS bytes FROM pg_stat_user_tables WHERE relname IN ('crawl_target','crawl_event','crawl_attempt') ORDER BY relname"))).mappings().all()
            return {**dict(stats), **dict(summary), "tables": [dict(row) for row in tables]}
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--hosts", type=int, default=10)
    parser.add_argument("--pages", type=int, default=200)
    parser.add_argument("--gap", type=float, default=0.5)
    parser.add_argument("--latency-ms", type=float, default=80)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--throttle-every", type=int, default=0)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--log", default="")
    args = parser.parse_args()

    url = os.environ.get("BENCH_DATABASE_URL", "")
    try:
        url = benchmark_database_url(url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    os.environ["DATABASE_URL"] = url
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

    def run(coroutine):
        if sys.platform == "win32":
            return asyncio.run(coroutine, loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
        return asyncio.run(coroutine)

    if args.worker:
        import logging
        logging.disable(logging.INFO)
        return run(worker(args))

    run(seed(args))
    before = run(database_snapshot())
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        log = os.path.join(folder, "requests.jsonl")
        forward = [str(item) for pair in (
            ("--concurrency", args.concurrency), ("--gap", args.gap), ("--latency-ms", args.latency_ms),
            ("--seconds", args.seconds), ("--throttle-every", args.throttle_every), ("--log", log),
        ) for item in pair]
        started = time.time()
        processes = [subprocess.Popen([sys.executable, __file__, "--worker", *forward],
                                      stdout=subprocess.DEVNULL) for _ in range(args.workers)]
        for process in processes:
            try:
                process.wait(timeout=args.seconds + 60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        time.sleep(0.2)
        report = summarize(log, args, time.time() - started)
        after = run(database_snapshot())
        report.update(worker_exit_codes=[process.returncode for process in processes],
                      database_before=before, database_after=after,
                      committed_transactions=after['xact_commit'] - before['xact_commit'],
                      updated_tuples=after['tup_updated'] - before['tup_updated'])
        print(json.dumps(report, indent=2))
    return int(any(report['worker_exit_codes']) or report['gap_violations'] > 0 or report['overlapping_requests'] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
