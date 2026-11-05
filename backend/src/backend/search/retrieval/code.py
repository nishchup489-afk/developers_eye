"""Code-only candidate retrieval from search_index.code_vector.

Uses PostgreSQL websearch_to_tsquery('simple', ...) so that phrase,
OR, and exclusion operators have the same query semantics as text FTS.
Scores are preliminary PostgreSQL scores; final ranking is BM25.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_QUERY_CHARS = 256
MAX_RESULTS = 100
MAX_OFFSET = 10_000


CANDIDATE_POOL = 20_000  # See search_text: bounds ranking work on common terms.


@dataclass(frozen=True, slots=True)
class CodeRetrievalHit:
    document_id: int
    score: float


_CODE_SEARCH_SQL = text(
    """
    WITH input_query AS (
        SELECT websearch_to_tsquery('simple', :query_text) AS tsq
    )
    SELECT
        si.document_id,
        ts_rank_cd(si.code_vector, input_query.tsq, 32)::float8 AS score
    FROM (
        SELECT candidate.document_id, candidate.code_vector
        FROM search_index AS candidate, input_query
        WHERE candidate.code_vector @@ input_query.tsq
          AND (CAST(:categories AS text[]) IS NULL OR candidate.category = ANY(CAST(:categories AS text[])))
        LIMIT :pool
    ) AS si
    CROSS JOIN input_query
    ORDER BY score DESC, si.document_id ASC
    LIMIT :limit OFFSET :offset
    """
)


def _validate_query(query: str) -> str:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    normalized = " ".join(query.split())
    if len(normalized) > MAX_QUERY_CHARS:
        raise ValueError(f"query must be at most {MAX_QUERY_CHARS} characters")
    if any(unicodedata.category(ch) == "Cc" for ch in normalized):
        raise ValueError("query contains unsupported control characters")
    return normalized


def _validate_pagination(limit: int, offset: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be an integer between 1 and {MAX_RESULTS}")
    if type(offset) is not int or not 0 <= offset <= MAX_OFFSET:
        raise ValueError(f"offset must be an integer between 0 and {MAX_OFFSET}")


async def search_code(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 50,
    offset: int = 0,
    categories: tuple[str, ...] | None = None,
) -> list[CodeRetrievalHit]:
    """Return code-vector candidates; never fetch documents or rank with BM25."""
    _validate_pagination(limit, offset)
    normalized = _validate_query(query)
    if not normalized:
        return []
    result = await session.execute(_CODE_SEARCH_SQL, {
        "query_text": normalized, "limit": limit, "offset": offset,
        "pool": CANDIDATE_POOL, "categories": list(categories) if categories is not None else None,
    })
    return [
        CodeRetrievalHit(document_id=int(row["document_id"]), score=float(row["score"]))
        for row in result.mappings().all()
    ]


__all__ = ["CodeRetrievalHit", "search_code"]
