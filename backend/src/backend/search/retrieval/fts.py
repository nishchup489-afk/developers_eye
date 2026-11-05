"""PostgreSQL full-text candidate retrieval for Developer's Eye.

The legacy combined retriever remains available for existing callers.
The dedicated search_text() function matches only search_vector.
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import SearchIndex
from backend.search.types import RetrievalHit

CANDIDATE_POOL = 20_000


async def get_full_text_search(
    query: str,
    session: AsyncSession,
    limit: int = 20,
) -> list[dict[str, int | float]]:
    """Legacy combined text+code retrieval, retained for existing callers."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    query = query.strip()
    if not query:
        return []
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    text_query = func.websearch_to_tsquery("english", query)
    code_query = func.websearch_to_tsquery("simple", query)
    text_match = SearchIndex.search_vector.bool_op("@@")(text_query)
    code_match = SearchIndex.code_vector.bool_op("@@")(code_query)
    search_rank = func.coalesce(
        func.ts_rank_cd(SearchIndex.search_vector, text_query), 0.0
    ).label("search_rank")
    code_rank = func.coalesce(
        func.ts_rank_cd(SearchIndex.code_vector, code_query), 0.0
    ).label("code_rank")
    stmt = (
        select(SearchIndex.document_id, search_rank, code_rank)
        .where(or_(text_match, code_match))
        .order_by(
            (search_rank + code_rank).desc(),
            SearchIndex.document_id.asc(),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        {
            "document_id": row.document_id,
            "search_rank": float(row.search_rank),
            "code_rank": float(row.code_rank),
        }
        for row in result
    ]


async def search_text(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 100,
    categories: tuple[str, ...] | None = None,
) -> list[RetrievalHit]:
    """Return text matches ranked provisionally by PostgreSQL.

    ts_rank_cd must read each matching vector, so ranking every match of a common
    word would take seconds at millions of documents. Ranking stops at
    CANDIDATE_POOL matches, and category filters apply before that limit.
    """
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    normalized = query.strip()
    if len(normalized) > 256:
        raise ValueError("query must not exceed 256 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if not normalized:
        return []

    tsquery = func.websearch_to_tsquery("english", normalized)
    matches = select(SearchIndex.document_id, SearchIndex.search_vector).where(
        SearchIndex.search_vector.bool_op("@@")(tsquery)
    )
    if categories is not None:
        matches = matches.where(SearchIndex.category.in_(categories))
    pool = matches.limit(CANDIDATE_POOL).subquery()
    score = func.ts_rank_cd(pool.c.search_vector, tsquery).label("score")
    statement = (
        select(pool.c.document_id, score)
        .order_by(score.desc(), pool.c.document_id.asc())
        .limit(limit)
    )
    rows = (await session.execute(statement)).all()
    return [
        RetrievalHit(document_id=int(row.document_id), search_rank=float(row.score))
        for row in rows
    ]


__all__ = ["get_full_text_search", "search_text"]
