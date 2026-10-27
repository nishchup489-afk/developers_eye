"""Independent polling worker for Developer's Eye PostgreSQL indexer.

Runs separately from crawler.worker.runner. No leases or claim table:
selector candidates are hints, and writer.py serializes/validates source writes.
Concurrent indexer processes may duplicate preparation work; they must not
corrupt the index. Cursor pagination avoids hot-looping on invalid documents.

Commands (from crawler/):
    poetry run python -m indexer.worker.runner --once
    poetry run python -m indexer.worker.runner --forever --batch-size 100 --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field, replace
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from indexer.config import IndexerConfig
from indexer.schemas import IndexCandidate, IndexResult, IndexStatus
from indexer.selector import select_index_candidates, select_removal_candidates
from indexer.service import index_candidate, remove_candidate

logger = logging.getLogger("indexer.worker.runner")


@dataclass(slots=True)
class BatchReport:
    selected: int = 0
    removals_selected: int = 0
    outcomes: Counter[str] = field(default_factory=Counter)
    elapsed_seconds: float = 0.0
    next_index_cursor: int = 0
    next_removal_cursor: int = 0
    end_of_index_scan: bool = False
    end_of_removal_scan: bool = False

    @property
    def failed(self) -> int:
        return self.outcomes[IndexStatus.FAILED.value]


async def _process_index(
    session_factory: async_sessionmaker[AsyncSession],
    candidate: IndexCandidate,
    config: IndexerConfig,
    semaphore: asyncio.Semaphore,
) -> IndexResult:
    async with semaphore:
        try:
            result = await index_candidate(session_factory, candidate, config=config)
            if not isinstance(result, IndexResult):
                raise TypeError("index_candidate must return IndexResult")
            logger.info("INDEX document=%s status=%s duration_ms=%.1f", candidate.document_id,
                        result.status.value, result.duration_ms)
            return result
        except Exception:
            logger.exception("INDEX FAILED document=%s", candidate.document_id)
            return IndexResult(document_id=candidate.document_id, status=IndexStatus.FAILED,
                               details="unexpected indexing failure; see worker logs")


async def _process_removal(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: int,
    semaphore: asyncio.Semaphore,
) -> IndexResult:
    async with semaphore:
        try:
            result = await remove_candidate(session_factory, document_id)
            if not isinstance(result, IndexResult):
                raise TypeError("remove_candidate must return IndexResult")
            logger.info("REMOVE document=%s status=%s duration_ms=%.1f", document_id,
                        result.status.value, result.duration_ms)
            return result
        except Exception:
            logger.exception("REMOVE FAILED document=%s", document_id)
            return IndexResult(document_id=document_id, status=IndexStatus.FAILED,
                               details="unexpected removal failure; see worker logs")


async def run_batch(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    config: IndexerConfig,
    index_cursor: int = 0,
    removal_cursor: int = 0,
) -> BatchReport:
    """Select one page of each work type, then process using separate sessions.

    IMPORTANT: selector.select_removal_candidates must honor after_document_id.
    See the bundled selector cursor patch if your version omits the predicate.
    """
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")
    for name, cursor in (("index_cursor", index_cursor), ("removal_cursor", removal_cursor)):
        if type(cursor) is not int or cursor < 0:
            raise ValueError(f"{name} must be a nonnegative integer")

    start = perf_counter()
    async with session_factory() as session:
        candidates = await select_index_candidates(
            session, config=config, after_document_id=index_cursor
        )
        removals = await select_removal_candidates(
            session, config=config, after_document_id=removal_cursor
        )

    semaphore = asyncio.Semaphore(config.concurrency)
    tasks = [
        _process_removal(session_factory, document_id, semaphore)
        for document_id in removals
    ] + [
        _process_index(session_factory, candidate, config, semaphore)
        for candidate in candidates
    ]
    results = await asyncio.gather(*tasks)

    outcomes = Counter(result.status.value for result in results)
    # Always advance past attempted documents, even on FAILED/STALE. Otherwise
    # a malformed document could cause an endless immediate retry loop.
    index_end = len(candidates) < config.batch_size
    removal_end = len(removals) < config.batch_size

    report = BatchReport(
        selected=len(candidates),
        removals_selected=len(removals),
        outcomes=outcomes,
        elapsed_seconds=perf_counter() - start,
        next_index_cursor=0 if index_end or not candidates else candidates[-1].document_id,
        next_removal_cursor=0 if removal_end or not removals else removals[-1],
        end_of_index_scan=index_end,
        end_of_removal_scan=removal_end,
    )
    logger.info(
        "BATCH index=%s removals=%s outcomes=%s duration=%.2fs next=(%s,%s)",
        report.selected, report.removals_selected, dict(outcomes),
        report.elapsed_seconds, report.next_index_cursor, report.next_removal_cursor,
    )
    return report


async def run_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    config: IndexerConfig,
    forever: bool = False,
) -> int:
    """Run once or poll indefinitely; return nonzero after any failed work."""
    index_cursor = removal_cursor = 0
    failures = 0
    cycles = 0
    logger.info("WORKER START mode=%s batch=%s concurrency=%s poll=%.1fs index_version=%s",
                "forever" if forever else "once", config.batch_size,
                config.concurrency, config.poll_seconds, config.index_version)
    try:
        while True:
            report = await run_batch(
                session_factory,
                config=config,
                index_cursor=index_cursor,
                removal_cursor=removal_cursor,
            )
            cycles += 1
            failures += report.failed
            index_cursor = report.next_index_cursor
            removal_cursor = report.next_removal_cursor
            if not forever:
                break

            # Poll after finishing both pages, even when documents failed.
            # Work remains in the DB and will be considered next scan.
            if report.end_of_index_scan and report.end_of_removal_scan:
                logger.info("SCAN COMPLETE; next scan after %.1fs", config.poll_seconds)
                await asyncio.sleep(config.poll_seconds)
    finally:
        logger.info("WORKER STOP cycles=%s failures=%s", cycles, failures)
    return 1 if failures else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Developer's Eye indexing worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one page (default)")
    mode.add_argument("--forever", action="store_true", help="Continuously poll")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--poll-seconds", type=float, default=None)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), default=None)
    return parser.parse_args(argv)


async def _main(config: IndexerConfig, forever: bool) -> int:
    from backend.db.session import SessionFactory, engine
    try:
        return await run_worker(SessionFactory, config=config, forever=forever)
    finally:
        await engine.dispose()


def main() -> None:
    args = parse_args()
    base = IndexerConfig.from_env()
    overrides = {
        name: value for name, value in (
            ("batch_size", args.batch_size),
            ("concurrency", args.concurrency),
            ("poll_seconds", args.poll_seconds),
            ("log_level", args.log_level),
        ) if value is not None
    }
    config = replace(base, **overrides)
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    try:
        raise SystemExit(asyncio.run(_main(config, forever=args.forever)))
    except KeyboardInterrupt:
        logger.info("Interrupted")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
