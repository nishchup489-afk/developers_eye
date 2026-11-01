from collections import Counter
import re
from typing import Iterable
import unicodedata

from backend.search.snippets.types import MAX_QUERY_TERMS, MAX_TERM_CHARS
from backend.search.snippets.validation import _normalize_terms, _pattern

def find_highlight_spans(
    text: str,
    query_terms: Iterable[str],
) -> tuple[tuple[int, int], ...]:
    """Return sorted, non-overlapping, end-exclusive highlight spans."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    pattern = _pattern(_normalize_terms(query_terms))

    if pattern is None:
        return ()

    return tuple(
        (match.start(), match.end())
        for match in pattern.finditer(text)
    )


def _score_with_pattern(
    passage: str,
    pattern: re.Pattern[str] | None,
) -> int:
    """Reward distinct term coverage and cap repeated-term influence."""
    if pattern is None:
        return 0

    counts = Counter(
        match.lastgroup
        for match in pattern.finditer(passage)
    )

    unique_score = 4 * len(counts)
    occurrence_score = sum(
        min(count, 3)
        for count in counts.values()
    )

    return unique_score + occurrence_score


def score_passage(
    passage: str,
    query_terms: Iterable[str],
) -> int:
    """Calculate relevance of one passage to the query terms."""
    if not isinstance(passage, str):
        raise TypeError("passage must be a string")

    pattern = _pattern(_normalize_terms(query_terms))

    return _score_with_pattern(passage, pattern)

