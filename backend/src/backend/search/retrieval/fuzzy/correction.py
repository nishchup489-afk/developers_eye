"""Conservative spelling suggestions, never silently rewritten searches."""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from backend.schema.search_term import QueryCorrection, TermCorrection
from backend.search.retrieval.fuzzy.candidates import find_fuzzy_candidates, get_exact_term

MAX_QUERY_CHARS = 256
MAX_QUERY_TOKENS = 12
_WHITESPACE = re.compile(r"(\s+)")
_PLAIN_WORD = re.compile(r"[A-Za-z]{4,32}\Z")
_SEARCH_OPERATORS = frozenset({"and", "or", "not"})


def _edit_distance(left: str, right: str) -> int:
    """Optimal string alignment distance (including adjacent transpositions)."""
    rows, cols = len(left), len(right)
    distances = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows + 1):
        distances[i][0] = i
    for j in range(cols + 1):
        distances[0][j] = j
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            cost = left[i - 1] != right[j - 1]
            distances[i][j] = min(
                distances[i - 1][j] + 1,
                distances[i][j - 1] + 1,
                distances[i - 1][j - 1] + int(cost),
            )
            if (i > 1 and j > 1
                and left[i - 1] == right[j - 2]
                and left[i - 2] == right[j - 1]):
                distances[i][j] = min(
                    distances[i][j], distances[i - 2][j - 2] + 1
                )
    return distances[rows][cols]


async def suggest_query_correction(query: str, session: AsyncSession) -> QueryCorrection:
    """Preserve technical identifiers and return a suggestion for eligible typos."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query must not exceed {MAX_QUERY_CHARS} characters")

    parts = _WHITESPACE.split(query)
    words = [part for part in parts if part and not part.isspace()]
    if len(words) > MAX_QUERY_TOKENS:
        return QueryCorrection(original_query=query, suggested_query=query)

    replacements: list[TermCorrection] = []
    in_quotes = False
    for index, part in enumerate(parts):
        if not part or part.isspace():
            continue
        quote_count = part.count('"') + part.count("'")
        quoted = in_quotes or quote_count > 0
        if quote_count % 2:
            in_quotes = not in_quotes
        if quoted or not _PLAIN_WORD.fullmatch(part):
            continue
        if any(ch.isupper() for ch in part[1:]) and not part.isupper():
            continue

        normalized = part.lower()
        if normalized in _SEARCH_OPERATORS:
            continue
        if await get_exact_term(normalized, session) is not None:
            continue

        candidates = await find_fuzzy_candidates(normalized, session, limit=20)
        max_distance = 1 if len(normalized) <= 6 else 2
        viable = [
            (candidate, distance)
            for candidate in candidates
            if candidate.term != normalized
            if _PLAIN_WORD.fullmatch(candidate.term)
            if (distance := _edit_distance(normalized, candidate.term)) <= max_distance
        ]
        if not viable:
            continue
        viable.sort(key=lambda item: (
            item[1], -item[0].similarity, -item[0].document_frequency, item[0].term
        ))
        chosen, distance = viable[0]
        parts[index] = chosen.term
        replacements.append(TermCorrection(
            original=part,
            replacement=chosen.term,
            similarity=chosen.similarity,
            edit_distance=distance,
        ))

    return QueryCorrection(
        original_query=query,
        suggested_query="".join(parts),
        corrections=replacements,
    )


__all__ = ["suggest_query_correction"]
