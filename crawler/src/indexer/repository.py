
"""PostgreSQL persistence operations for Developer's Eye search indexes.

The writer owns the transaction and all indexing decisions. This module only
reads, locks, upserts, and deletes rows through a supplied AsyncSession.

IMPORTANT: get_document_for_update() and upsert_search_index() must run in the
same transaction. The writer must compare the locked document's source_id,
updated_at, and availability with SearchVectors before calling the UPSERT.

Storage mapping:
    SearchVectors.text_vector -> SearchIndex.search_vector (existing column)
    SearchVectors.code_vector -> SearchIndex.code_vector (migration required)

Never commit or roll back here; those decisions belong to the writer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from indexer.vector import SearchVectors

_INDEX_HASH = re.compile(r"v[1-9][0-9]*:[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredIndexState:
    """Small projection of the current index row, without loading TSVECTORs."""

    document_id: int
    indexed_hash: str
    indexed_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class LockedDocumentState:
    """Document revision locked until the caller's transaction ends."""

    document_id: int
    source_id: int
    is_available: bool
    updated_at: datetime


def _require_document_id(document_id: int) -> None:
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")


async def get_search_index(
    session: AsyncSession, document_id: int
) -> StoredIndexState | None:
    """Read index freshness metadata; no locks, writes, or vector payloads."""
    _require_document_id(document_id)

    statement = select(
        SearchIndex.document_id,
        SearchIndex.indexed_hash,
        SearchIndex.indexed_at,
    ).where(SearchIndex.document_id == document_id)

    row = (await session.execute(statement)).one_or_none()

    if row is None:
        return None

    return StoredIndexState(
        document_id=row.document_id,
        indexed_hash=row.indexed_hash,
        indexed_at=row.indexed_at,
    )


async def get_document_for_update(
    session: AsyncSession, document_id: int
) -> LockedDocumentState | None:
    """Lock the source revision within the writer-owned transaction.

    PostgreSQL SELECT ... FOR UPDATE serializes changes to this document row.
    Do not use SKIP LOCKED: the writer must see the row or wait for its lock.
    Never commit between this call and upsert_search_index().
    """
    _require_document_id(document_id)

    statement = (
        select(
            Document.id,
            Document.source_id,
            Document.is_available,
            Document.updated_at,
        )
        .where(Document.id == document_id)
        .with_for_update(of=Document)
    )

    row = (await session.execute(statement)).one_or_none()

    if row is None:
        return None

    return LockedDocumentState(
        document_id=row.id,
        source_id=row.source_id,
        is_available=row.is_available,
        updated_at=row.updated_at,
    )


async def get_index_lexemes(session: AsyncSession, document_id: int) -> tuple[str, ...]:
    """Read distinct stored lexemes, not original source content."""
    _require_document_id(document_id)
    statement = select(
        func.tsvector_to_array(
            SearchIndex.search_vector.op("||", return_type=SearchIndex.search_vector.type)(
                SearchIndex.code_vector
            )
        )
    ).where(SearchIndex.document_id == document_id)
    lexemes = (await session.execute(statement)).scalar_one_or_none()
    return tuple(lexemes) if lexemes is not None else ()


async def upsert_search_index(
    session: AsyncSession,
    vectors: SearchVectors,
    *,
    indexed_hash: str,
) -> int:
    """Persist vector expressions with a PostgreSQL INSERT ... ON CONFLICT.

    REQUIRES the writer to have locked and validated the corresponding source
    document in the same transaction. This function does not check freshness,
    claim work, commit, or turn SQLAlchemy expressions into Python values.

    Return the inserted/updated document ID. DB exceptions propagate.
    """
    if not isinstance(vectors, SearchVectors):
        raise TypeError("vectors must be SearchVectors")

    _require_document_id(vectors.document_id)

    if not isinstance(indexed_hash, str) or _INDEX_HASH.fullmatch(indexed_hash) is None:
        raise ValueError("indexed_hash must have format vN:<64 lowercase hex digits>")

    statement = insert(SearchIndex).values(
        document_id=vectors.document_id,
        search_vector=vectors.text_vector,
        code_vector=vectors.code_vector,
        indexed_hash=indexed_hash,
        indexed_at=func.now(),
    )

    statement = statement.on_conflict_do_update(
        index_elements=[SearchIndex.document_id],
        set_={
            "search_vector": statement.excluded.search_vector,
            "code_vector": statement.excluded.code_vector,
            "indexed_hash": statement.excluded.indexed_hash,
            "indexed_at": func.now(),
        },
    ).returning(SearchIndex.document_id)

    return (await session.execute(statement)).scalar_one()


async def delete_search_index(session: AsyncSession, document_id: int) -> bool:
    """Delete one index row. Return False if already absent (idempotent).

    The writer must protect deletion against a concurrent source change.
    Hard-deleted documents normally cascade through the existing foreign key.
    """
    _require_document_id(document_id)

    statement = (
        delete(SearchIndex)
        .where(SearchIndex.document_id == document_id)
        .returning(SearchIndex.document_id)
    )

    return (await session.scalar(statement)) is not None


__all__ = [
    "StoredIndexState",
    "LockedDocumentState",
    "get_search_index",
    "get_index_lexemes",
    "get_document_for_update",
    "upsert_search_index",
    "delete_search_index",
]
