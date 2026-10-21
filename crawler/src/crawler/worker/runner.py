"""Developer's Eye - database-backed crawler worker runner.

Runner responsibilities:
  1. Recover expired target leases.
  2. Claim a bounded batch from the PostgreSQL frontier.
  3. COMMIT the claims before any network I/O.
  4. Dispatch each claimed target to crawler.worker.jobs.process_job().
  5. Log job outcomes and optionally poll for more jobs.

The job handler owns fetch/parse/process, attempt records, and finalization.
It must validate lease ownership before committing results.

IMPORTANT: This is NOT the rollback-only live-pipeline test. It commits
frontier lease updates, and the job handler may commit documents.

Required public contract in crawler/worker/jobs.py:

    async def process_job(target: CrawlTargetRead) -> JobResult:
        ...

The implementation of process_job must use its own database sessions. Never
share the claim transaction's AsyncSession across concurrent jobs.

Examples (from repository root after setting PYTHONPATH):
    python -m crawler.worker.runner --once
    python -m crawler.worker.runner --once --batch-size 5 --concurrency 2
    python -m crawler.worker.runner --forever --poll-seconds 10
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import selectors
import sys
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from functools import partial

from crawler.worker.logging_config import setup_logging
from crawler.policy_and_politeness.politeness_policy import (PolitenessManager,)
from backend.db.session import SessionFactory, engine
from backend.schema.crawler_frontier import CrawlTargetRead
from crawler.schedular.repository import claim_targets, recover_expired_leases
from crawler.worker.telemetry import WorkerMonitor, active_targets, checkpoint
from crawler.worker.recovery import recover_failed_claim
from backend.models.crawl_attempt import CrawlAttempt
from sqlalchemy import select

logger = logging.getLogger("crawler.worker.runner")

# A job handler is responsible for making the crawl outcome durable.
# JobResult can be used as the return type once jobs.py is implemented.
JobHandler = Callable[[CrawlTargetRead], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    batch_size: int = 5
    concurrency: int = 2
    lease_seconds: int = 300
    job_timeout_seconds: int = 240
    poll_seconds: float = 10.0
    source_id: int | None = None
    forever: bool = False

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if self.lease_seconds < 30:
            raise ValueError("lease_seconds must be >= 30")
        if self.job_timeout_seconds <= 0:
            raise ValueError("job_timeout_seconds must be positive")
        if self.job_timeout_seconds > self.lease_seconds - 15:
            raise ValueError(
                "job_timeout_seconds must leave at least 15 seconds "
                "before lease expiration for finalization"
            )
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if self.source_id is not None and self.source_id <= 0:
            raise ValueError("source_id must be positive")


@dataclass(slots=True)
class BatchReport:
    recovered: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    timed_out: int = 0
    outcomes: Counter[str] = field(default_factory=Counter)
    elapsed_seconds: float = 0.0


async def claim_batch(config: RunnerConfig) -> tuple[int, list[CrawlTargetRead]]:
    """Recover old leases and commit new claims in a short transaction.

    Never return live SQLAlchemy ORM objects beyond the session. Copy them to
    immutable-ish Pydantic read schemas while the session is still open.
    """
    async with SessionFactory() as session:
        async with session.begin():
            recovered = await recover_expired_leases(session)
            # Do not lease more than can start immediately. Pending tasks
            # behind a semaphore would burn their lease while waiting.
            claim_limit = min(config.batch_size, config.concurrency)
            rows = await claim_targets(
                session=session,
                limit=claim_limit,
                lease_seconds=config.lease_seconds,
                source_id=config.source_id,
            )
            targets = [CrawlTargetRead.model_validate(row) for row in rows]

    # Leaving session.begin() normally commits these claims.
    # All expensive work happens AFTER this point.
    return recovered, targets


async def execute_target(
    target: CrawlTargetRead,
    *,
    job_handler: JobHandler,
    semaphore: asyncio.Semaphore,
    config: RunnerConfig,
    report: BatchReport,
) -> None:
    """Run a single claimed job, recording the outcome, not finalizing it.

    The job handler is responsible for its own database transactions and
    attempt records. Runner failures are left to lease-expiry recovery.
    """
    async with semaphore:
        started = time.perf_counter()
        targets = active_targets.get()
        if targets is not None:
            targets[target.id] = {"target_id": target.id, "source_id": target.source_id, "url": target.fetch_url}
        logger.info(
            "START target=%s source=%s url=%s lease_until=%s",
            target.id, target.source_id, target.fetch_url, target.lease_until,
        )

        try:
            # A deadline prevents one hung job from blocking the entire batch.
            # Jobs must finalize before the actual lease expires.
            async with asyncio.timeout(config.job_timeout_seconds):
                result = await job_handler(target)

            if result is None or not hasattr(result, "outcome"):
                raise TypeError(
                    "process_job must return a JobResult with an 'outcome' field"
                )

            outcome = str(getattr(result.outcome, "value", result.outcome))
            report.outcomes[outcome] += 1

            if outcome in {"success", "not_modified"}:
                report.succeeded += 1
            elif outcome in {"failed", "error"}:
                report.failed += 1

            logger.info(
                "DONE target=%s outcome=%s status=%s docs=%s links=%s "
                "duration=%.2fs",
                target.id,
                outcome,
                getattr(result, "http_status", None),
                getattr(result, "documents_saved", 0),
                getattr(result, "links_enqueued", 0),
                time.perf_counter() - started,
            )

        except TimeoutError:
            await record_runner_failure(target, "timeout", "Job deadline exceeded; retry scheduled")
            report.timed_out += 1
            report.failed += 1
            logger.error(
                "TIMEOUT target=%s after=%ss; lease will be recovered "
                "after expiration if job did not finalize",
                target.id, config.job_timeout_seconds,
            )

        except Exception as exc:
            await record_runner_failure(target, "worker", f"{type(exc).__name__}: {exc}"[:1000])
            report.failed += 1
            logger.exception(
                "CRASH target=%s; lease recovery will retry if not finalized",
                target.id,
            )

        finally:
            if targets is not None:
                targets.pop(target.id, None)

        # Do not catch asyncio.CancelledError: shutdown cancels tasks;
        # the lease expiry mechanism requeues unfinished claims.


async def run_batch(
    *,
    config: RunnerConfig,
    job_handler: JobHandler,
) -> BatchReport:
    """Claim one committed batch and execute its jobs concurrently."""
    started = time.perf_counter()
    report = BatchReport()

    report.recovered, targets = await claim_batch(config)
    report.claimed = len(targets)

    logger.info(
        "CLAIM recovered=%s claimed=%s limit=%s concurrency=%s",
        report.recovered, report.claimed, config.batch_size, config.concurrency,
    )

    if targets:
        semaphore = asyncio.Semaphore(config.concurrency)
        await asyncio.gather(*(
            execute_target(
                target,
                job_handler=job_handler,
                semaphore=semaphore,
                config=config,
                report=report,
            )
            for target in targets
        ))

    report.elapsed_seconds = time.perf_counter() - started
    logger.info(
        "BATCH recovered=%s claimed=%s succeeded=%s failed=%s "
        "timed_out=%s outcomes=%s duration=%.2fs",
        report.recovered,
        report.claimed,
        report.succeeded,
        report.failed,
        report.timed_out,
        dict(report.outcomes),
        report.elapsed_seconds,
    )
    return report


async def record_runner_failure(target: CrawlTargetRead, category: str, message: str) -> None:
    await recover_failed_claim(SessionFactory, target.id, target.lease_until, category, message)


async def run_worker(*, config: RunnerConfig, job_handler: JobHandler) -> int:
    try:
        async with WorkerMonitor(config):
            return await _run_worker(config=config, job_handler=job_handler)
    finally:
        await engine.dispose()


async def _run_worker(
    *,
    config: RunnerConfig,
    job_handler: JobHandler,
) -> int:
    """Run one batch or poll continuously until interrupted."""
    cycles = 0
    total_claimed = 0
    total_failed = 0

    logger.info(
        "WORKER START mode=%s batch_size=%s concurrency=%s lease=%ss",
        "forever" if config.forever else "once",
        config.batch_size, config.concurrency, config.lease_seconds,
    )

    try:
        while True:
            report = await run_batch(config=config, job_handler=job_handler)
            cycles += 1
            total_claimed += report.claimed
            total_failed += report.failed

            if not config.forever:
                break

            # Poll even after processing a batch, but avoid a sleep when work
            # is available: newly discovered targets can be claimed immediately.
            if report.claimed == 0:
                logger.info("IDLE no eligible targets; sleeping %.1fs", config.poll_seconds)
                await asyncio.sleep(config.poll_seconds)

    finally:
        logger.info(
            "WORKER STOP cycles=%s claimed=%s job_failures=%s",
            cycles, total_claimed, total_failed,
        )

    return 1 if total_failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Developer's Eye frontier worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Claim and run one batch (default)")
    mode.add_argument("--forever", action="store_true", help="Continuously poll for jobs")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--job-timeout-seconds", type=int, default=240)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--source-id", type=int, default=None)
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args()


def load_job_handler() -> JobHandler:
    """Import the implementation lazily so --help still works if absent."""
    try:
        from crawler.worker.jobs import process_job
    except ImportError as exc:
        raise RuntimeError(
            "Implement and export async process_job(target: CrawlTargetRead) "
            "from crawler.worker.jobs before running the worker. "
            "Your repository's jobs.py currently has no implementation."
        ) from exc

    if not callable(process_job):
        raise TypeError("crawler.worker.jobs.process_job must be callable")
    return process_job


async def main(config: RunnerConfig) -> int:

    # Automatically register new JSON sources and queue eligible website seeds.
    # Existing source slugs and crawl targets are not duplicated.
    try:
        from crawler.seed.seed import seed_sources
        from crawler.seed.discovery import discover_initial_targets

        await seed_sources()
        queued = await discover_initial_targets()
        logger.info("SOURCE SYNC complete queued_start_urls=%s", queued)
    except Exception:
        logger.exception("SOURCE SYNC failed; worker startup aborted")
        await engine.dispose()
        return 1

    # STEP 1: Create one shared politeness manager.
    politeness_manager = PolitenessManager(
        max_concurrent_per_host=1,
        min_interval_seconds=2.0,
    )

    # STEP 2: Bind the required dependency to process_job.
    job_handler = partial(
        load_job_handler(),
        politeness_manager=politeness_manager,
    )

    # STEP 3: Start the worker.
    return await run_worker(
        config=config,
        job_handler=job_handler,
    )


if __name__ == "__main__":
    args = parse_args()

    setup_logging(args.log_level)
    config = RunnerConfig(
        batch_size=args.batch_size,
        concurrency=args.concurrency,
        lease_seconds=args.lease_seconds,
        job_timeout_seconds=args.job_timeout_seconds,
        poll_seconds=args.poll_seconds,
        source_id=args.source_id,
        forever=args.forever,
    )
    if sys.platform == "win32":
        exit_code = asyncio.run(
            main(config),
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    else:
        exit_code = asyncio.run(main(config))
    raise SystemExit(exit_code)
