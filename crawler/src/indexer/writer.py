"""Atomic, concurrency-safe search-index persistence for Developer's Eye.

Requires repository.py with get_document_for_update, get_search_index,
upsert_search_index and delete_search_index. Writer owns transactions;
repository functions neither commit nor roll back.

A caller must provide its own async_sessionmaker (not a shared AsyncSession).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from indexer.repository import (
    delete_search_index,
    get_document_for_update,
    get_search_index,
    get_index_lexemes,
    upsert_search_index,
)
from indexer.vocabulary import synchronize_vocabulary
from indexer.schemas import IndexStatus
from indexer.vector import SearchVectors


async def persist_search_vectors(
    session_factory: async_sessionmaker[AsyncSession],
    vectors: SearchVectors,
    *,
    indexed_hash: str,
) -> IndexStatus:
    """Persist prepared vector expressions only for their original revision.

    SELECT ... FOR UPDATE on the source document serializes source changes
    and competing index writers. The lock is held until the transaction ends.
    Rebuilding is skipped only if the stored hash matches AND the index
    timestamp is not older than the locked document revision.
    """
    if not isinstance(vectors, SearchVectors):
        raise TypeError("vectors must be SearchVectors")
    if not isinstance(indexed_hash, str) or not indexed_hash:
        raise ValueError("indexed_hash must be a nonempty string")

    async with session_factory() as session:
        async with session.begin():
            source = await get_document_for_update(session, vectors.document_id)
            if (
                source is None
                or not source.is_available
                or source.source_id != vectors.source_id
                or source.updated_at != vectors.source_updated_at
            ):
                return IndexStatus.STALE

            existing = await get_search_index(session, vectors.document_id)
            if (
                existing is not None
                and existing.indexed_hash == indexed_hash
                and existing.indexed_at >= source.updated_at
            ):
                return IndexStatus.UNCHANGED

            old_lexemes = await get_index_lexemes(session, vectors.document_id)
            await upsert_search_index(
                session,
                vectors,
                indexed_hash=indexed_hash,
            )
            new_lexemes = await get_index_lexemes(session, vectors.document_id)
            await synchronize_vocabulary(
                session, old_lexemes=old_lexemes, new_lexemes=new_lexemes
            )
            return IndexStatus.INDEXED


async def remove_search_index(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: int,
) -> IndexStatus:
    """Remove an index only if its source is missing or unavailable.

    Hard deletions normally cascade via the FK; a missing index is harmless.
    A revived source must not lose its index due to an old removal candidate.
    """
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")

    async with session_factory() as session:
        async with session.begin():
            source = await get_document_for_update(session, document_id)
            if source is not None and source.is_available:
                return IndexStatus.STALE

            old_lexemes = await get_index_lexemes(session, document_id)
            removed = await delete_search_index(session, document_id)
            if removed:
                await synchronize_vocabulary(
                    session, old_lexemes=old_lexemes, new_lexemes=()
                )
            return IndexStatus.REMOVED if removed else IndexStatus.SKIPPED


__all__ = ["persist_search_vectors", "remove_search_index"]
