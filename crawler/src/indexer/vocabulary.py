"""Maintain fuzzy-search vocabulary from already-indexed PostgreSQL lexemes.

This module never reads or tokenizes source document text. The indexer writer
passes lexemes extracted from search_index TSVECTOR columns, and owns the
transaction. Counts represent documents containing each term, not occurrences.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import delete, update, select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.search_terms import SearchTerm
from backend.models.search_index import SearchIndex

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
    """Apply per-document frequency deltas within the caller's transaction.

    Lock terms in consistent alphabetical order across concurrent writers.
    Missing decrement rows indicate vocabulary drift and abort the transaction.
    """
    old_terms = vocabulary_terms(old_lexemes)
    new_terms = vocabulary_terms(new_lexemes)
    changes = {term: -1 for term in old_terms - new_terms}
    changes.update({term: 1 for term in new_terms - old_terms})

    for term in sorted(changes):
        if changes[term] == 1:
            statement = insert(SearchTerm).values(term=term, document_frequency=1)
            statement = statement.on_conflict_do_update(
                index_elements=[SearchTerm.term],
                set_={"document_frequency": SearchTerm.document_frequency + 1},
            )
            await session.execute(statement)
            continue

        result = await session.execute(
            update(SearchTerm)
            .where(SearchTerm.term == term, SearchTerm.document_frequency > 0)
            .values(document_frequency=SearchTerm.document_frequency - 1)
            .returning(SearchTerm.document_frequency)
        )
        remaining = result.scalar_one_or_none()
        if remaining is None:
            raise RuntimeError(f"Vocabulary count drift detected for {term!r}")
        if remaining == 0:
            await session.execute(
                delete(SearchTerm).where(
                    SearchTerm.term == term,
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
