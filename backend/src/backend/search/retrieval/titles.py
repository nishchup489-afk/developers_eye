"""Title-match candidate retrieval (EXP-0017).

The text channel keeps the 100 best documents by weighted ts_rank. A long page
that repeats the query words in its body outranks the short reference page
whose title *is* the query ("Optional chaining - JavaScript | MDN"), so that
page can miss the candidate pool entirely and no reranker can recover it.

This channel adds up to TITLE_CANDIDATES documents that match the whole query
(same websearch semantics, operators included) and whose title, the A-weighted
part of search_vector, contains at least half of the query's lexemes. They are
ordered by how many query lexemes the title holds, then by shorter titles.
Scores are preliminary; BM25 still ranks the merged pool.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.search.retrieval.fts import CANDIDATE_POOL
from backend.search.types import RetrievalHit

TITLE_CANDIDATES = 30
MAX_QUERY_CHARS = 256

_TITLE_SQL = text(
    """
    WITH input_query AS (
        SELECT
            websearch_to_tsquery('english', :query_text) AS tsq,
            tsvector_to_array(to_tsvector('english', :query_text)) AS lexemes
    ), pool AS (
        SELECT candidate.document_id, ts_filter(candidate.search_vector, '{a}') AS title
        FROM search_index AS candidate, input_query
        WHERE candidate.search_vector @@ input_query.tsq
          AND (CAST(:categories AS text[]) IS NULL OR candidate.category = ANY(CAST(:categories AS text[])))
        LIMIT :pool
    ), scored AS (
        SELECT
            pool.document_id,
            cardinality(ARRAY(
                SELECT unnest(tsvector_to_array(pool.title))
                INTERSECT
                SELECT unnest(input_query.lexemes)
            )) AS title_hits,
            length(pool.title) AS title_length,
            cardinality(input_query.lexemes) AS query_lexemes
        FROM pool CROSS JOIN input_query
    )
    SELECT document_id, title_hits::float8 / query_lexemes AS score
    FROM scored
    WHERE query_lexemes > 0 AND title_hits * 2 >= query_lexemes AND title_hits > 0
    ORDER BY title_hits DESC, title_length ASC, document_id ASC
    LIMIT :limit
    """
)


async def search_titles(
    session: AsyncSession,
    query: str,
    *,
    limit: int = TITLE_CANDIDATES,
    categories: tuple[str, ...] | None = None,
) -> list[RetrievalHit]:
    """Return full-query matches whose titles cover most query lexemes."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    normalized = query.strip()
    if len(normalized) > MAX_QUERY_CHARS:
        raise ValueError(f"query must not exceed {MAX_QUERY_CHARS} characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if not normalized:
        return []
    rows = (await session.execute(_TITLE_SQL, {
        "query_text": normalized,
        "limit": limit,
        "pool": CANDIDATE_POOL,
        "categories": list(categories) if categories is not None else None,
    })).all()
    return [
        RetrievalHit(document_id=int(row.document_id), search_rank=float(row.score))
        for row in rows
    ]


__all__ = ["TITLE_CANDIDATES", "search_titles"]
