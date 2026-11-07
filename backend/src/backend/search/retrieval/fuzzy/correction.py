"""Conservative spelling suggestions, never silently rewritten searches.

The vocabulary holds English stems ("configur", "librari") next to unstemmed
code tokens. A suggestion must be a readable word, so each candidate is
expanded into surface forms (stem + common suffixes), and a form other than the
bare candidate is kept only when PostgreSQL's english_stem reduces it back to
that candidate. The form closest to what the user typed wins, so
"configuraton" suggests "configuration", not the stem "configur".
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from backend.schema.search_term import QueryCorrection, TermCorrection
from backend.search.retrieval.fuzzy.candidates import (
    english_stems,
    find_fuzzy_candidates,
    get_exact_term,
)

MAX_QUERY_CHARS = 256
MAX_QUERY_TOKENS = 12
_WHITESPACE = re.compile(r"(\s+)")
_PLAIN_WORD = re.compile(r"[A-Za-z]{4,32}\Z")
_SEARCH_OPERATORS = frozenset({"and", "or", "not"})
# Suffixes Snowball strips; stem + suffix rebuilds a readable word.
_SUFFIXES = (
    "", "e", "s", "es", "ed", "ing", "er", "ers", "ion", "ions", "ation",
    "ations", "ate", "ated", "ates", "ive", "ity", "ment", "ments", "al",
    "ally", "ly", "ness", "able", "ence", "ance", "ent", "ism", "ist", "ize",
    "ized", "ous", "ure", "ures", "ory",
)
# A stem ending in "i" came from "y" ("librari" <- "library").
_I_SUFFIXES = ("y", "ies", "ied")


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


def surface_forms(stem: str) -> list[str]:
    """Readable words that may reduce to a stem; the stem itself comes first."""
    forms = [stem + suffix for suffix in _SUFFIXES]
    if stem.endswith("i"):
        forms += [stem[:-1] + suffix for suffix in _I_SUFFIXES]
    return [form for form in dict.fromkeys(forms) if _PLAIN_WORD.fullmatch(form)]


async def _is_known(word: str, session: AsyncSession) -> bool:
    """True when the word, or the English stem the index stores for it, exists."""
    if await get_exact_term(word, session) is not None:
        return True
    # "configuration" is indexed as "configur": a known stem is not a typo.
    stem = (await english_stems([word], session)).get(word)
    return bool(stem) and stem != word and await get_exact_term(stem, session) is not None


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
        if await _is_known(normalized, session):
            continue

        candidates = [
            candidate
            for candidate in await find_fuzzy_candidates(normalized, session, limit=20)
            if candidate.term != normalized
            if _PLAIN_WORD.fullmatch(candidate.term)
        ]
        if not candidates:
            continue
        expanded = {candidate.term: surface_forms(candidate.term) for candidate in candidates}
        stems = await english_stems(
            [form for forms in expanded.values() for form in forms], session
        )
        max_distance = 1 if len(normalized) <= 6 else 2
        viable = []
        for candidate in candidates:
            for form in expanded[candidate.term]:
                bare = form == candidate.term
                if bare:
                    # The bare term may be an unstemmed code token, so keep
                    # it, except a stem ending in "i" ("librari"), never a word.
                    if form.endswith("i") and stems.get(form) == form:
                        continue
                elif stems.get(form) != candidate.term:
                    continue
                if form == normalized:
                    continue
                distance = _edit_distance(normalized, form)
                if distance <= max_distance:
                    viable.append((distance, not bare, candidate, form))
        if not viable:
            continue
        viable.sort(key=lambda item: (
            item[0], item[1], -item[2].similarity, -item[2].document_frequency, item[3]
        ))
        distance, _, chosen, form = viable[0]
        parts[index] = form
        replacements.append(TermCorrection(
            original=part,
            replacement=form,
            similarity=chosen.similarity,
            edit_distance=distance,
        ))

    return QueryCorrection(
        original_query=query,
        suggested_query="".join(parts),
        corrections=replacements,
    )


__all__ = ["suggest_query_correction", "surface_forms"]
