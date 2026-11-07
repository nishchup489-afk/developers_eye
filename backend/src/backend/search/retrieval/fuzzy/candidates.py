"""Read vocabulary-based fuzzy candidates from search_terms via pg_trgm.

The offline indexer owns vocabulary mutation. Query-serving code reads only.
Requires PostgreSQL pg_trgm extension and the existing GIN trigram index.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import ARRAY, Text, bindparam, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.search_terms import SearchTerm
from backend.schema.search_term import FuzzyCandidate, SearchTermRead

MAX_TERM_CHARS = 128
# Transaction-local pg_trgm similarity threshold for candidate lookup.
TRIGRAM_THRESHOLD = 0.2


def normalize_term(term: str) -> str:
    if not isinstance(term, str):
        raise TypeError("term must be a string")
    return term.strip().lower()


async def get_exact_term(term: str, session: AsyncSession) -> SearchTermRead | None:
    normalized = normalize_term(term)
    if not normalized or len(normalized) > MAX_TERM_CHARS:
        return None
    record = await session.scalar(select(SearchTerm).where(SearchTerm.term == normalized))
    return SearchTermRead.model_validate(record) if record is not None else None


async def find_fuzzy_candidates(
    term: str,
    session: AsyncSession,
    *,
    limit: int = 20,
) -> list[FuzzyCandidate]:
    """Find similar vocabulary lexemes; correction logic decides which to use."""
    normalized = normalize_term(term)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer between 1 and 50")
    if len(normalized) < 3 or len(normalized) > MAX_TERM_CHARS:
        return []
    # pg_trgm's default 0.3 drops short transpositions ("pyhton" vs "python"
    # is 0.27); edit distance in correction.py keeps the precision.
    await session.execute(select(func.set_config(
        "pg_trgm.similarity_threshold", str(TRIGRAM_THRESHOLD), True
    )))
    similarity = func.similarity(SearchTerm.term, normalized).label("similarity")
    statement = (
        select(SearchTerm.term, SearchTerm.document_frequency, similarity)
        .where(SearchTerm.term.bool_op("%")(normalized))
        .order_by(similarity.desc(), SearchTerm.document_frequency.desc(), SearchTerm.term.asc())
        .limit(limit)
    )
    rows = (await session.execute(statement)).all()
    return [
        FuzzyCandidate(
            term=row.term,
            document_frequency=int(row.document_frequency),
            similarity=float(row.similarity),
        )
        for row in rows
    ]


async def english_stems(words: Iterable[str], session: AsyncSession) -> dict[str, str | None]:
    """Map each word to its english_stem lexeme (None for a stop word).

    The English index stores stems ("configur", "librari"), so suggestions use
    this to check that a readable word reduces to an indexed stem.
    """
    unique = sorted({normalize_term(word) for word in words} - {""})
    if not unique:
        return {}
    statement = text(
        "SELECT word, ts_lexize('english_stem', word) FROM unnest(:words) AS word"
    ).bindparams(bindparam("words", type_=ARRAY(Text())))
    rows = (await session.execute(statement, {"words": unique})).all()
    return {row[0]: (row[1][0] if row[1] else None) for row in rows}


async def upsert_term_frequencies(
    frequencies: Mapping[str, int], session: AsyncSession
) -> int:
    """Legacy absolute-frequency utility, not used by the online search service."""
    if not isinstance(frequencies, Mapping):
        raise TypeError("frequencies must be a mapping")
    normalized: dict[str, int] = {}
    for raw_term, frequency in frequencies.items():
        term = normalize_term(raw_term)
        if not term or len(term) > MAX_TERM_CHARS:
            raise ValueError("term length must be between 1 and 128")
        if type(frequency) is not int or frequency < 0:
            raise ValueError("document frequency must be a non-negative integer")
        if term in normalized and normalized[term] != frequency:
            raise ValueError("conflicting frequencies for normalized term")
        normalized[term] = frequency
    if not normalized:
        return 0
    expired = [term for term, count in normalized.items() if count == 0]
    active = [
        {"term": term, "document_frequency": count}
        for term, count in normalized.items() if count > 0
    ]
    if expired:
        await session.execute(delete(SearchTerm).where(SearchTerm.term.in_(expired)))
    for start in range(0, len(active), 1000):
        stmt = insert(SearchTerm).values(active[start:start + 1000])
        await session.execute(stmt.on_conflict_do_update(
            index_elements=[SearchTerm.term],
            set_={"document_frequency": stmt.excluded.document_frequency},
        ))
    return len(normalized)


__all__ = [
    "normalize_term",
    "get_exact_term",
    "find_fuzzy_candidates",
    "english_stems",
    "upsert_term_frequencies",
]
