from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import func , select , insert , count, true

from backend.models.search_index import SearchIndex

async def _get_total_number_of_indexed_document(
        session : AsyncSession ,

) -> int :
    stmt = (
        select(func.count()).select_from(SearchIndex)
    )

    count = await session.scalar(stmt)

    return count


async def _number_of_document_containing_term_t(
        session : AsyncSession , 
        term : str ,
        mode : str
):
    search_tsq = func.plainto_tsquery('english' , term)
    search_stmt = (
        select(func.count()).select_from(SearchIndex)
        .where(SearchIndex.search_vector.op('@@')(search_tsq) ).label('document_frequency')
    )

    code_tsq = func.websearch_to_tsquery('simple' , term)
    code_stmt = (
        select(func.count()).select_from(SearchIndex)
        .where(SearchIndex.code_vector.op('@@')(code_tsq))
    )

    if mode == "TEXT":
        count = await session.scalar(search_stmt)
    elif mode == "CODE":
        count = await session.scalar(code_stmt)

    return count

def _get_vector(mode: str):
    if mode == "TEXT":
        return SearchIndex.search_vector
    if mode == "CODE":
        return SearchIndex.code_vector

    raise ValueError("mode must be TEXT or CODE")


async def _get_term_frequency(
    session: AsyncSession,
    document_id: int,
    term: str,
    mode: str,
) -> int | None:
    """Count stored occurrences of a term in one document."""

    vector = _get_vector(mode)

    t = (
        func.unnest(vector)
        .table_valued("lexeme", "positions", "weights")
        .lateral("t")
    )

    stmt = (
        select(
            func.coalesce(
                func.sum(func.cardinality(t.c.positions))
                .filter(t.c.lexeme == term),
                0,
            )
        )
        .select_from(SearchIndex)
        .outerjoin(t, true())
        .where(SearchIndex.document_id == document_id)
        .group_by(SearchIndex.document_id)
    )

    result = await session.scalar(stmt)
    return None if result is None else int(result)


async def _get_document_length(
    session: AsyncSession,
    document_id: int,
    mode: str,
) -> int | None:
    """Count stored token occurrences in one indexed document."""

    vector = _get_vector(mode)

    t = (
        func.unnest(vector)
        .table_valued("lexeme", "positions", "weights")
        .lateral("t")
    )

    stmt = (
        select(
            func.coalesce(
                func.sum(func.cardinality(t.c.positions)),
                0,
            )
        )
        .select_from(SearchIndex)
        .outerjoin(t, true())
        .where(SearchIndex.document_id == document_id)
        .group_by(SearchIndex.document_id)
    )

    result = await session.scalar(stmt)
    return None if result is None else int(result)



async def _get_average_document_length(
    session: AsyncSession,
    mode: str,
) -> float:
    """Calculate average indexed document length for BM25."""

    vector = _get_vector(mode)

    t = (
        func.unnest(vector)
        .table_valued("lexeme", "positions", "weights")
        .lateral("t")
    )

    # Calculate the length of each document.
    document_lengths = (
        select(
            SearchIndex.document_id,
            func.coalesce(
                func.sum(func.cardinality(t.c.positions)),
                0,
            ).label("document_length"),
        )
        .select_from(SearchIndex)
        .outerjoin(t, true())
        .group_by(SearchIndex.document_id)
        .subquery()
    )

    # Calculate the average across all indexed documents.
    stmt = select(
        func.coalesce(
            func.avg(document_lengths.c.document_length),
            0.0,
        )
    )

    result = await session.scalar(stmt)

    return float(result)
