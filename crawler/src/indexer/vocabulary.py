"""Maintain fuzzy-search vocabulary from already-indexed PostgreSQL lexemes.

This module never reads or tokenizes source document text. The indexer writer
passes lexemes extracted from search_index TSVECTOR columns, and owns the
transaction. Counts represent documents containing each term, not occurrences.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from sqlalchemy import delete, update, select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.search_terms import SearchTerm
from backend.models.search_index import SearchIndex

logger = logging.getLogger(__name__)

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
    """Synchronize document frequencies atomically.

    The caller must hold the shared vocabulary advisory lock
    and manage the surrounding database transaction.
    """

    old_terms = vocabulary_terms(old_lexemes)
    new_terms = vocabulary_terms(new_lexemes)

    added = sorted(new_terms - old_terms)
    removed = sorted(old_terms - new_terms)

    if not added and not removed:
        return

    batch_size = 500

    # Increment new terms exactly once per document.
    for start in range(0, len(added), batch_size):
        batch = added[start:start + batch_size]

        stmt = insert(SearchTerm).values([
            {"term": term, "document_frequency": 1}
            for term in batch
        ])

        stmt = stmt.on_conflict_do_update(
            index_elements=[SearchTerm.term],
            set_={
                "document_frequency":
                    SearchTerm.document_frequency + 1
            },
        )

        await session.execute(stmt)

    # Decrement terms no longer present in this document.
    for start in range(0, len(removed), batch_size):
        batch = removed[start:start + batch_size]

        stmt = (
            update(SearchTerm)
            .where(
                SearchTerm.term.in_(batch),
                SearchTerm.document_frequency > 0,
            )
            .values(
                document_frequency=
                    SearchTerm.document_frequency - 1
            )
            .returning(
                SearchTerm.term,
                SearchTerm.document_frequency,
            )
        )

        rows = (await session.execute(stmt)).all()
        updated = {term: count for term, count in rows}

        missing = set(batch) - updated.keys()

        if missing:
            # The vocabulary is derived data and vocabulary_rebuild repairs it.
            # Drift must never stop a real index or availability change.
            logger.warning(
                "Vocabulary frequency drift on %d terms, sample=%s",
                len(missing), sorted(missing)[:5],
            )

        zero_terms = [
            term
            for term, count in updated.items()
            if count == 0
        ]

        if zero_terms:
            await session.execute(
                delete(SearchTerm).where(
                    SearchTerm.term.in_(zero_terms),
                    SearchTerm.document_frequency == 0,
                )
            )


__all__ = ["vocabulary_terms", "synchronize_vocabulary", "lock_vocabulary", "remove_indexed_documents"]

# One transaction-level mutex coordinates writers, crawler deletions and rebuild.
# The number is an application-owned advisory-lock key (not a table lock).
_VOCABULARY_LOCK_KEY = 7331090042


async def lock_vocabulary(session: AsyncSession) -> None:
    """Serialize vocabulary-changing transactions and one-time rebuilds."""
    await session.execute(select(func.pg_advisory_xact_lock(_VOCABULARY_LOCK_KEY)))


async def remove_indexed_documents(
    session: AsyncSession, document_ids: Iterable[int]
) -> int:
    """Delete index rows and decrement frequencies in the same transaction.

    The caller must lock affected Document rows first, in ascending ID order.
    This supports 404/410, noindex, and normal index removals.
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
