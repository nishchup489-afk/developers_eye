"""Safely request reindexing without deleting live search vectors.

A requested reindex changes ONLY existing search_index.indexed_hash values to
'reindex:pending'. The existing searchable vectors remain in place while the
normal selector and worker rebuild them. Documents with no index already appear
in selector results, so nothing needs to be marked for those documents.

Document row locks serialize marking with writer.py's parent-row locks.
This is an explicit operator operation, not a background queue/lease system.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.documents import Document
from backend.models.search_index import SearchIndex

logger = logging.getLogger("indexer.reindex")
MARKER = "reindex:pending"


def _validate_ids(document_ids: Sequence[int]) -> tuple[int, ...]:
    if isinstance(document_ids, (str, bytes)) or not isinstance(document_ids, Sequence):
        raise TypeError("document_ids must be a sequence of integers")
    values = tuple(document_ids)
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError("document IDs must be positive integers")
    return tuple(sorted(set(values)))


async def mark_for_reindex(
    session: AsyncSession,
    document_ids: Sequence[int],
    *,
    dry_run: bool = False,
) -> list[int]:
    """Mark existing indexes of available documents inside caller's transaction.

    IMPORTANT: caller must use `async with session.begin()` and commit.
    Locks are obtained in ascending document-id order. A missing index is not
    counted (it is already eligible for initial indexing).
    """
    ids = _validate_ids(document_ids)
    if not ids:
        return []

    statement = (
        select(Document.id)
        .join(SearchIndex, SearchIndex.document_id == Document.id)
        .where(Document.id.in_(ids), Document.is_available.is_(True))
        .order_by(Document.id)
    )
    if not dry_run:
        statement = statement.with_for_update(of=Document)
    eligible = list((await session.scalars(statement)).all())

    if eligible and not dry_run:
        await session.execute(
            update(SearchIndex)
            .where(SearchIndex.document_id.in_(eligible))
            .values(indexed_hash=MARKER)
        )
    return eligible


async def mark_all_for_reindex(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    """Mark all existing available indexes, paging by document ID.

    Each batch is committed separately. Do not run concurrently with another
    mass reindex command. The worker may index entries during this operation.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= 10_000:
        raise ValueError("batch_size must be an integer between 1 and 10000")

    cursor = 0
    marked = 0
    while True:
        async with session_factory() as session:
            async with session.begin():
                ids = list((await session.scalars(
                    select(Document.id)
                    .join(SearchIndex, SearchIndex.document_id == Document.id)
                    .where(Document.is_available.is_(True), Document.id > cursor)
                    .order_by(Document.id)
                    .limit(batch_size)
                )).all())
                if ids:
                    matched = await mark_for_reindex(session, ids, dry_run=dry_run)
                    marked += len(matched)

        if not ids:
            break
        cursor = ids[-1]
        logger.info("REINDEX MARK cursor=%s count=%s", cursor, len(ids))
        if len(ids) < batch_size:
            break
    return marked


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mark documents for asynchronous reindexing")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--document-id", action="append", type=int)
    target.add_argument("--all", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    from backend.db.session import SessionFactory, engine

    try:
        if args.all:
            changed = await mark_all_for_reindex(
                SessionFactory, batch_size=args.batch_size, dry_run=args.dry_run
            )
        else:
            async with SessionFactory() as session:
                async with session.begin():
                    changed = len(await mark_for_reindex(
                        session, args.document_id, dry_run=args.dry_run
                    ))
        print(f"{'Eligible' if args.dry_run else 'Marked'}: {changed} existing index rows")
        print("Start the indexer runner to rebuild them; no vectors were deleted.")
        return 0
    finally:
        await engine.dispose()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(asyncio.run(run_cli(args)))


if __name__ == "__main__":
    main()
