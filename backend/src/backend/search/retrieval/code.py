"""Code-oriented candidate retrieval from Developer's Eye's PostgreSQL index.

This module reads only ``search_index.code_vector``. It does not query the
``document`` table, perform typo correction, or compute the final BM25 rank.

The indexer must have populated ``code_vector`` with the PostgreSQL ``simple``
text-search configuration. Punctuation-sensitive exact-symbol lookup requires
an additional index and is outside this first implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


MAX_QUERY_CHARS = 512
MAX_RESULTS = 100
MAX_OFFSET = 10_000


@dataclass(frozen=True, slots=True)
class CodeRetrievalHit:
    """A code-search candidate; ``score`` is NOT a BM25 score."""

    document_id: int
    score: float


# One query object is reused across requests; only bound parameters vary.
# ``plainto_tsquery`` handles input safely and uses the same 'simple' config
# as the stored code_vector. It ANDs the lexemes in a multi-token query.
_CODE_SEARCH_SQL = text(
    """
    WITH input_query AS (
        SELECT plainto_tsquery('simple', :query_text) AS tsq
    )
    SELECT
        si.document_id,
        ts_rank_cd(si.code_vector, input_query.tsq, 32)::float8 AS score
    FROM search_index AS si
    CROSS JOIN input_query
    WHERE si.code_vector @@ input_query.tsq
    ORDER BY score DESC, si.document_id ASC
    LIMIT :limit
    OFFSET :offset
    """
)


def _validate_query(query: str) -> str:
    if not isinstance(query, str):
        raise TypeError("query must be a string")

    # Normalizing whitespace avoids treating newlines/tabs as query syntax.
    normalized = " ".join(query.split())
    if len(normalized) > MAX_QUERY_CHARS:
        raise ValueError(f"query must be at most {MAX_QUERY_CHARS} characters")
    if any(unicodedata.category(char) == "Cc" for char in normalized):
        raise ValueError("query contains unsupported control characters")
    return normalized


def _validate_pagination(limit: int, offset: int) -> None:
    # bool is a subclass of int in Python; reject it explicitly.
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
) -> list[CodeRetrievalHit]:
    """Return candidates whose indexed code lexemes match every query lexeme.

    Args:
        session: Existing SQLAlchemy async session; ownership stays with caller.
        query: Raw query text, processed with PostgreSQL's ``simple`` config.
        limit: Number of candidates to retrieve, from 1 to 100.
        offset: Number of candidates to skip, from 0 to 10,000.

    Returns:
        Hits sorted by preliminary cover-density rank (descending), then
        document ID (ascending) for deterministic pagination.

    Notes:
        No database request is sent for an empty or whitespace-only query.
        Results are retrieval candidates, not finalized search results.
        The upstream query router should decide when to call this retriever.
    """
    _validate_pagination(limit, offset)
    normalized = _validate_query(query)
    if not normalized:
        return []

    result = await session.execute(
        _CODE_SEARCH_SQL,
        {
            "query_text": normalized,
            "limit": limit,
            "offset": offset,
        },
    )

    return [
        CodeRetrievalHit(
            document_id=int(row["document_id"]),
            score=float(row["score"]),
        )
        for row in result.mappings().all()
    ]
