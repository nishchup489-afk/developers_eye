from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import SearchIndex


async def get_full_text_search(
    query: str,
    session: AsyncSession,
    limit: int = 20,
) -> list[dict[str, int | float]]:

    if not isinstance(query, str):
        raise TypeError("query must be a string")

    query = query.strip()

    if not query:
        return []

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 100
    ):
        raise ValueError("limit must be between 1 and 100")

    # Convert user query into PostgreSQL TSQUERY expressions.
    text_query = func.websearch_to_tsquery("english", query)
    code_query = func.websearch_to_tsquery("simple", query)

    # Match indexed terms using PostgreSQL @@ operator.
    text_match = SearchIndex.search_vector.bool_op("@@")(text_query)
    code_match = SearchIndex.code_vector.bool_op("@@")(code_query)

    # Calculate independent relevance scores.
    search_rank = func.coalesce(
        func.ts_rank_cd(SearchIndex.search_vector, text_query),
        0.0,
    ).label("search_rank")

    code_rank = func.coalesce(
        func.ts_rank_cd(SearchIndex.code_vector, code_query),
        0.0,
    ).label("code_rank")

    # Retrieve matching documents.
    stmt = (
        select(
            SearchIndex.document_id,
            search_rank,
            code_rank,
        )
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