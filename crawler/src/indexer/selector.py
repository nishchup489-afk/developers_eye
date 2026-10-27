"""Read-only selection of Developer's Eye indexing and removal work.

A candidate is a *hint*, not a claim: workers must reload the document and
validate freshness when writing an index. This module deliberately never
commits, acquires long-lived locks, or modifies database rows.

Freshness contract:
- Every change to an index-relevant Document field updates Document.updated_at.
- SearchIndex.indexed_at records a completed, successfully persisted build.
- SearchIndex.indexed_hash begins with IndexerConfig.index_hash_prefix.
- Document.last_seen_at is not an indexing trigger.
"""

from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from indexer.config import IndexerConfig
from indexer.schemas import IndexCandidate


def _check_document_id(document_id: int) -> None:
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")


def _check_cursor(after_document_id: int) -> None:
    if type(after_document_id) is not int or after_document_id < 0:
        raise ValueError("after_document_id must be a nonnegative integer")


def _outdated_index_condition(config: IndexerConfig):
    """SQL predicate for an absent, outdated, or old-version search index."""
    return or_(
        SearchIndex.document_id.is_(None),
        SearchIndex.indexed_at < Document.updated_at,
        ~SearchIndex.indexed_hash.startswith(config.index_hash_prefix),
    )


async def is_index_current(
    session: AsyncSession,
    document_id: int,
    *,
    config: IndexerConfig,
) -> bool:
    """True only when an available document has a current-version search row.

    A missing or unavailable document returns False. This is a point-in-time
    read: the writer must still guard against concurrent document changes.
    """
    _check_document_id(document_id)

    statement = (
        select(
            Document.is_available,
            Document.updated_at,
            SearchIndex.indexed_at,
            SearchIndex.indexed_hash,
        )
        .outerjoin(SearchIndex, SearchIndex.document_id == Document.id)
        .where(Document.id == document_id)
    )
    row = (await session.execute(statement)).one_or_none()

    if row is None or not row.is_available or row.indexed_at is None:
        return False

    return (
        row.indexed_at >= row.updated_at
        and row.indexed_hash is not None
        and row.indexed_hash.startswith(config.index_hash_prefix)
    )


async def select_index_candidates(
    session: AsyncSession,
    *,
    config: IndexerConfig,
    after_document_id: int = 0,
) -> list[IndexCandidate]:
    """Select at most config.batch_size documents needing an index build.

    Keyset pagination avoids OFFSET costs. The caller should advance the
    cursor to the final candidate's document_id, then reset it to zero once
    the scan yields no rows. Rows are not reserved for this worker.
    """
    _check_cursor(after_document_id)

    statement = (
        select(Document.id, Document.updated_at)
        .outerjoin(SearchIndex, SearchIndex.document_id == Document.id)
        .where(
            Document.id > after_document_id,
            Document.is_available.is_(True),
            _outdated_index_condition(config),
        )
        .order_by(Document.id.asc())
        .limit(config.batch_size)
    )

    result = await session.execute(statement)
    return [
        IndexCandidate(document_id=doc_id, source_updated_at=updated_at)
        for doc_id, updated_at in result.all()
    ]


async def select_removal_candidates(
    session: AsyncSession,
    *,
    config: IndexerConfig,
    after_document_id: int = 0,
) -> list[int]:
    """Select unavailable documents that still have searchable index rows.

    Deleted document rows are handled by the search_index foreign key's
    ON DELETE CASCADE. This query handles soft-unavailable documents.
    """
    _check_cursor(after_document_id)

    statement = (
        select(SearchIndex.document_id)
        .select_from(SearchIndex)
        .outerjoin(
            Document,
            Document.id == SearchIndex.document_id,
        )
        .where(
            or_(
                Document.id.is_(None),
                Document.is_available.is_(False),
            )
        )
        .order_by(SearchIndex.document_id)
        .limit(config.batch_size)
    )

    return list((await session.scalars(statement)).all())
