"""Maintain fuzzy-search vocabulary from already-indexed PostgreSQL lexemes.

This module never reads or tokenizes source document text. The indexer writer
passes lexemes extracted from search_index TSVECTOR columns, and owns the
transaction. Counts represent documents containing each term, not occurrences.

search_terms is updated through a transactional outbox. Each index write adds a
vocabulary_change row in its own transaction, and one drainer at a time folds
those rows into search_terms. Counts are exact, and they trail the index by at
most one drain cycle, which is fine for spelling suggestions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.search_index import SearchIndex
from backend.models.search_terms import VocabularyChange

_TERM = re.compile(r"[a-z][a-z0-9_+.#-]*\Z", re.ASCII)
_SPECIAL = {"c++", "c#", "f#", ".net"}
_ARTIFACT_EXTENSIONS = frozenset({"zip", "tar", "gz", "tgz", "pdf", "epub", "whl"})


def vocabulary_terms(lexemes: Iterable[str]) -> frozenset[str]:
    """Filter and deduplicate lexemes used by fuzzy retrieval.

    English-index terms are stems. This is not a natural-language spelling
    dictionary; suggestions must remain compatible with indexed lexemes.
    """
    selected: set[str] = set()
    for original in lexemes:
        if not isinstance(original, str):
            raise TypeError("lexemes must contain strings")
        term = original.casefold()
        if not 2 <= len(term) <= 64:
            continue
        if term not in _SPECIAL and _TERM.fullmatch(term) is None:
            continue
        if term.endswith((".", "-", "_")):
            continue
        if term.count(".") > 1 or term.count("-") > 2:
            continue
        if "." in term and term.rsplit(".", 1)[-1] in _ARTIFACT_EXTENSIONS:
            continue
        if sum(char.isascii() and char.isalpha() for char in term) < 2 and term not in _SPECIAL:
            continue
        if sum(char.isdigit() for char in term) > max(2, len(term) // 2):
            continue
        selected.add(term)
    return frozenset(selected)



async def synchronize_vocabulary(
    session: AsyncSession,
    *,
    old_lexemes: Iterable[str],
    new_lexemes: Iterable[str],
) -> None:
    """Record one document's vocabulary change in the caller's transaction.

    This appends to vocabulary_change and takes no shared lock, so index writers
    never wait for each other. drain_vocabulary_changes() applies the counts.
    """
    old_terms = vocabulary_terms(old_lexemes)
    new_terms = vocabulary_terms(new_lexemes)

    added = sorted(new_terms - old_terms)
    removed = sorted(old_terms - new_terms)

    if added or removed:
        session.add(VocabularyChange(added=added, removed=removed))
        await session.flush()


__all__ = [
    "vocabulary_terms",
    "synchronize_vocabulary",
    "lock_vocabulary",
    "remove_indexed_documents",
    "drain_vocabulary_changes",
]

# Held by whoever writes search_terms: one drain at a time, or a rebuild.
# The number is an application-owned advisory-lock key (not a table lock).
_VOCABULARY_LOCK_KEY = 7331090042
DRAIN_BATCH_SIZE = 2_000

_COLLECT = text("""
    CREATE TEMP TABLE vocabulary_delta ON COMMIT DROP AS
    WITH batch AS (
        DELETE FROM vocabulary_change
        WHERE id IN (SELECT id FROM vocabulary_change ORDER BY id LIMIT :limit)
        RETURNING added, removed
    ), deltas AS (
        SELECT unnest(added) AS term, 1 AS delta FROM batch
        UNION ALL
        SELECT unnest(removed), -1 FROM batch
    )
    SELECT term, sum(delta)::integer AS delta FROM deltas
    GROUP BY term HAVING sum(delta) <> 0
""")
_APPLY = (
    text("""
        UPDATE search_terms t
        SET document_frequency = GREATEST(t.document_frequency + d.delta, 0)
        FROM vocabulary_delta d WHERE t.term = d.term
    """),
    text("""
        INSERT INTO search_terms (term, document_frequency)
        SELECT d.term, d.delta FROM vocabulary_delta d
        WHERE d.delta > 0 AND NOT EXISTS (SELECT 1 FROM search_terms t WHERE t.term = d.term)
    """),
    text("""
        DELETE FROM search_terms t USING vocabulary_delta d
        WHERE t.term = d.term AND t.document_frequency = 0
    """),
)


async def lock_vocabulary(session: AsyncSession) -> None:
    """Wait for exclusive write access to search_terms (rebuilds only)."""
    await session.execute(select(func.pg_advisory_xact_lock(_VOCABULARY_LOCK_KEY)))


async def _drain_batch(session: AsyncSession, limit: int) -> int | None:
    if not await session.scalar(select(func.pg_try_advisory_xact_lock(_VOCABULARY_LOCK_KEY))):
        return None
    pending = await session.scalar(select(func.count()).select_from(
        select(VocabularyChange.id).limit(limit).subquery()
    ))
    if pending:
        await session.execute(_COLLECT, {"limit": limit})
        for statement in _APPLY:
            await session.execute(statement)
    return pending


async def drain_vocabulary_changes(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = DRAIN_BATCH_SIZE,
) -> int:
    """Apply queued changes to search_terms; returns how many were applied.

    Deltas are summed per term, so a common word is written once per batch, not
    once per document. Any indexer can call this: if another one is draining,
    this returns at once. Each batch commits together with its queue deletes,
    so a crash can neither lose a change nor apply one twice.
    """
    drained = 0
    while True:
        async with session_factory() as session:
            async with session.begin():
                pending = await _drain_batch(session, batch_size)
        if not pending:
            return drained
        drained += pending
        if pending < batch_size:
            return drained


async def remove_indexed_documents(
    session: AsyncSession, document_ids: Iterable[int]
) -> int:
    """Delete index rows and decrement frequencies in the same transaction.

    The caller must lock affected Document rows first, in ascending ID order.
    This supports 404/410, noindex, and normal index removals. It returns before
    the vocabulary counts change: those follow on the next drain.
    """
    ids = sorted(set(document_ids))
    if not ids:
        return 0
    if any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError("document IDs must be positive integers")
    rows = (await session.execute(
        select(
            SearchIndex.document_id,
            func.tsvector_to_array(
                SearchIndex.search_vector.op(
                    "||", return_type=SearchIndex.search_vector.type
                )(SearchIndex.code_vector)
            ),
        ).where(SearchIndex.document_id.in_(ids)).order_by(SearchIndex.document_id)
    )).all()
    for document_id, lexemes in rows:
        await session.execute(
            delete(SearchIndex).where(SearchIndex.document_id == document_id)
        )
        await synchronize_vocabulary(
            session, old_lexemes=lexemes or (), new_lexemes=()
        )
    return len(rows)
