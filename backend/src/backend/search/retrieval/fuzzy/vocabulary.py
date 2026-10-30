"""Exact vocabulary reads and authoritative frequency upserts.

The indexer, not the query-serving layer, owns frequency maintenance.
A frequency is the number of indexed documents containing the term.
Writes do not commit; the caller controls the transaction.
"""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.search_terms import SearchTerm
from backend.schema.search_term import SearchTermRead

MAX_TERM_CHARS = 128


def normalize_term(term: str) -> str:
    """Normalize vocabulary keys consistently for reads and writes."""
    if not isinstance(term, str):
        raise TypeError("term must be a string")
    return term.strip().lower()


async def get_exact_term(
    term: str, session: AsyncSession
) -> SearchTermRead | None:
    """Look up a term exactly using the primary-key B-tree index."""
    normalized = normalize_term(term)
    if not normalized or len(normalized) > MAX_TERM_CHARS:
        return None

    stmt = select(SearchTerm).where(SearchTerm.term == normalized)
    record = await session.scalar(stmt)
    return SearchTermRead.model_validate(record) if record is not None else None


async def upsert_term_frequencies(
    frequencies: Mapping[str, int], session: AsyncSession
) -> int:
    """Set absolute document frequencies supplied by the offline indexer.

    Zero-frequency terms are removed. This is not an increment operation:
    reprocessing an existing document must not inflate frequencies.
    Terms absent from this batch remain unchanged.
    """
    if not isinstance(frequencies, Mapping):
        raise TypeError("frequencies must be a mapping")

    normalized: dict[str, int] = {}
    for raw_term, frequency in frequencies.items():
        term = normalize_term(raw_term)
        if not term or len(term) > MAX_TERM_CHARS:
            raise ValueError("term length must be between 1 and 128")
        if isinstance(frequency, bool) or not isinstance(frequency, int):
            raise TypeError("document frequency must be an integer")
        if frequency < 0:
            raise ValueError("document frequency cannot be negative")
        if term in normalized and normalized[term] != frequency:
            raise ValueError("conflicting frequencies for normalized term")
        normalized[term] = frequency

    if not normalized:
        return 0

    expired = [term for term, count in normalized.items() if count == 0]
    active = [
        {"term": term, "document_frequency": count}
        for term, count in normalized.items()
        if count > 0
    ]

    if expired:
        await session.execute(delete(SearchTerm).where(SearchTerm.term.in_(expired)))

    # Batch to stay below PostgreSQL's bind-parameter limits.
    for start in range(0, len(active), 1000):
        statement = insert(SearchTerm).values(active[start : start + 1000])
        statement = statement.on_conflict_do_update(
            index_elements=[SearchTerm.term],
            set_={"document_frequency": statement.excluded.document_frequency},
        )
        await session.execute(statement)

    return len(normalized)
