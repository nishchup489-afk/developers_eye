"""Extract PostgreSQL-normalized positive query lexemes for BM25.

PostgreSQL remains responsible for parsing and linguistic normalization.
The parser below only reads PostgreSQL's canonical TSQUERY representation:
negated terms are excluded, while AND/OR/phrase terms are retained.

Retrieval must continue using the complete TSQUERY expression so that
negation, OR, and phrase constraints affect matching, not just scoring.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sqlalchemy import Text, cast, func, literal, select
from sqlalchemy.dialects.postgresql import REGCONFIG

from backend.search.config import SearchConfig
from backend.search.query_analyzer.analyzer import analyze_query

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# TSQUERY text output quotes lexemes and uses !, &, |, (), <->, and <N>.
# Handle both doubled quotes and backslash-escaped characters in lexemes.
_TSQUERY_TOKEN = re.compile(
    r"\s*(?:'(?P<term>(?:''|\\.|[^'\\])*)'(?:\:[A-D*]+)?"
    r"|(?P<operator><->|<\d+>|[!&|()]))"
)
_MAX_QUERY_TERMS = 32  # Must match ranking/statistics.py.


def _decode_lexeme(value: str) -> str:
    """Unescape a lexeme from PostgreSQL's printable TSQUERY format."""
    result: list[str] = []
    i = 0
    while i < len(value):
        if i + 1 < len(value) and value[i] == "'" and value[i + 1] == "'":
            result.append("'")
            i += 2
        elif value[i] == "\\" and i + 1 < len(value):
            result.append(value[i + 1])
            i += 2
        else:
            result.append(value[i])
            i += 1
    return "".join(result)


def _positive_lexemes(tsquery: str) -> tuple[str, ...]:
    """Get positive lexemes from PostgreSQL's canonical TSQUERY text.

    This is a bag of scoring terms, not a replacement for TSQUERY matching.
    Query operators continue to be enforced by the retrieval engine.
    """
    if not isinstance(tsquery, str):
        raise TypeError("tsquery must be a string")

    if not tsquery.strip():
        return ()

    # Each scope records whether the enclosing expression is negated.
    negated_scopes = [False]
    pending_not = False
    terms: dict[str, None] = {}
    offset = 0

    while offset < len(tsquery):
        if tsquery[offset:].isspace():
            break
        token = _TSQUERY_TOKEN.match(tsquery, offset)
        if token is None:
            raise ValueError("Unexpected PostgreSQL TSQUERY representation")
        offset = token.end()

        raw_term = token.group("term")
        if raw_term is not None:
            term = _decode_lexeme(raw_term)
            if term and not (negated_scopes[-1] ^ pending_not):
                terms[term] = None
                if len(terms) > _MAX_QUERY_TERMS:
                    raise ValueError("Too many distinct positive query lexemes")
            pending_not = False
            continue

        operator = token.group("operator")
        if operator == "!":
            pending_not = not pending_not
        elif operator == "(":
            negated_scopes.append(negated_scopes[-1] ^ pending_not)
            pending_not = False
        elif operator == ")":
            if len(negated_scopes) == 1 or pending_not:
                raise ValueError("Malformed PostgreSQL TSQUERY expression")
            negated_scopes.pop()
        else:
            if pending_not:
                raise ValueError("Malformed PostgreSQL TSQUERY expression")
            # &, |, <->, and <N> separate clauses, but do not change sign.

    if len(negated_scopes) != 1 or pending_not:
        raise ValueError("Malformed PostgreSQL TSQUERY expression")
    return tuple(terms)


async def tokenize_query(
    session: AsyncSession,
    query: str,
    *,
    config: SearchConfig | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (text_lexemes, code_lexemes) using one PostgreSQL round trip.

    Text uses the same English configuration as search_vector;
    code uses the same Simple configuration as code_vector.
    The input may contain OR, negative terms, or quoted phrases.
    """
    if config is None:
        config = SearchConfig()
    if not isinstance(config, SearchConfig):
        raise TypeError("config must be SearchConfig")

    normalized = analyze_query(query, config=config)

    def tsquery_text(search_config: str):
        return cast(
            func.websearch_to_tsquery(
                cast(literal(search_config, type_=Text()), REGCONFIG()),
                literal(normalized, type_=Text()),
            ),
            Text(),
        )

    stmt = select(
        tsquery_text(config.text_search_config).label("text_query"),
        tsquery_text(config.code_search_config).label("code_query"),
    )

    row = (await session.execute(stmt)).one()
    return (
        _positive_lexemes(row.text_query),
        _positive_lexemes(row.code_query),
    )


__all__ = ["tokenize_query"]
