"""One-shot, transactionally consistent vocabulary backfill/drift repair.

Run from crawler/:
    poetry run python -m indexer.vocabulary_rebuild --once
    poetry run python -m indexer.vocabulary_rebuild --progress-every 1000

Stop crawler and indexer writers before a rebuild. This is a maintenance
command, not a polling worker: normal indexing maintains counts afterward.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter
from time import perf_counter

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.search_index import SearchIndex
from backend.models.search_terms import SearchTerm, VocabularyChange
from indexer.vocabulary import lock_vocabulary, vocabulary_terms
from indexer.worker.runner import setup_logging

logger = logging.getLogger("indexer.vocabulary_rebuild")


async def rebuild_vocabulary(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    progress_every: int = 1000,
    write_batch_size: int = 500,
) -> tuple[int, int]:
    """Recount indexed lexemes and atomically replace term frequencies.

    The transaction-level advisory lock coordinates with participating writers.
    Stop all crawler and indexer writers before running this maintenance task,
    including deletion paths that may not yet acquire the shared lock.
    """
    if type(progress_every) is not int or progress_every <= 0:
        raise ValueError("progress_every must be a positive integer")
    if type(write_batch_size) is not int or write_batch_size <= 0:
        raise ValueError("write_batch_size must be a positive integer")

    started = perf_counter()
    async with session_factory() as session:
        async with session.begin():
            await lock_vocabulary(session)
            query = select(
                func.tsvector_to_array(
                    SearchIndex.search_vector.op(
                        "||", return_type=SearchIndex.search_vector.type
                    )(SearchIndex.code_vector)
                )
            ).order_by(SearchIndex.document_id)

            counts: Counter[str] = Counter()
            documents = 0
            result = await session.stream(query)
            try:
                async for (lexemes,) in result:
                    documents += 1
                    counts.update(vocabulary_terms(lexemes or ()))
                    if documents % progress_every == 0:
                        logger.info(
                            "[bold blue]SCAN[/] documents=%s unique_terms=%s duration=%.2fs",
                            documents, len(counts), perf_counter() - started,
                        )
            finally:
                await result.close()

            logger.info(
                "[bold blue]SCAN COMPLETE[/] documents=%s unique_terms=%s duration=%.2fs",
                documents, len(counts), perf_counter() - started,
            )

            # Replace counts in the same transaction. Until COMMIT, other
            # transactions cannot observe this intermediate table state.
            await session.execute(delete(SearchTerm))
            await session.execute(delete(VocabularyChange))
            sorted_terms = sorted(counts.items())
            total_batches = (
                len(sorted_terms) + write_batch_size - 1
            ) // write_batch_size

            for batch_number, offset in enumerate(
                range(0, len(sorted_terms), write_batch_size), start=1
            ):
                rows = [
                    {"term": term, "document_frequency": frequency}
                    for term, frequency in sorted_terms[
                        offset:offset + write_batch_size
                    ]
                ]
                await session.execute(insert(SearchTerm), rows)
                logger.info(
                    "[cyan]WRITE[/] batch=%s/%s terms=%s/%s",
                    batch_number,
                    total_batches,
                    min(offset + len(rows), len(sorted_terms)),
                    len(sorted_terms),
                )

            if not sorted_terms:
                logger.info("[dim]WRITE[/] no vocabulary terms found")

    # session.begin() committed successfully; counts are now visible.
    return documents, len(counts)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Developer's Eye one-shot vocabulary rebuild"
    )
    parser.add_argument(
        "--once", action="store_true", help="Run one rebuild (default)"
    )
    parser.add_argument(
        "--progress-every", type=_positive_int, default=1000,
        metavar="DOCUMENTS",
        help="Log scan progress every N indexed documents (default: 1000)",
    )
    parser.add_argument(
        "--write-batch-size", type=_positive_int, default=500,
        metavar="TERMS",
        help="Number of vocabulary terms written per batch (default: 500)",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    return parser.parse_args(argv)


async def _run(*, progress_every: int, write_batch_size: int) -> tuple[int, int]:
    # Import lazily so --help works without initializing database settings.
    from backend.db.session import SessionFactory, engine

    try:
        return await rebuild_vocabulary(
            SessionFactory,
            progress_every=progress_every,
            write_batch_size=write_batch_size,
        )
    finally:
        await engine.dispose()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)
    started = perf_counter()
    logger.info(
        "[bold cyan]VOCABULARY REBUILD START[/] mode=once "
        "progress_every=%s write_batch_size=%s",
        args.progress_every, args.write_batch_size,
    )
    try:
        documents, terms = asyncio.run(
            _run(
                progress_every=args.progress_every,
                write_batch_size=args.write_batch_size,
            )
        )
    except KeyboardInterrupt:
        logger.warning("[yellow]VOCABULARY REBUILD INTERRUPTED[/]")
        raise SystemExit(130) from None
    except Exception:
        logger.exception("[bold red]VOCABULARY REBUILD FAILED[/] rolled_back=true")
        raise SystemExit(1) from None

    logger.info(
        "[bold green]VOCABULARY REBUILD COMPLETE[/] "
        "documents=%s unique_terms=%s duration=%.2fs",
        documents, terms, perf_counter() - started,
    )


if __name__ == "__main__":
    main()
