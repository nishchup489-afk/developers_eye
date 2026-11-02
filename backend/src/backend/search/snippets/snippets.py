
"""Query-aware snippet generation for Developer's Eye.

Generates relevant, bounded excerpts from extracted document text.
No database access, SQL execution, or HTML generation.
"""

from __future__ import annotations

import re
from typing import Iterable

from backend.search.snippets.ranking import _score_with_pattern
from .types import Snippet, Passage
from .validation import _normalize_terms, _pattern, _positive_integer, normalize_snippet_text





def _window(
    text: str,
    match_start: int,
    max_chars: int,
    *,
    preserve_code: bool,
) -> Passage:
    """Extract a bounded passage around a matching position."""
    length = len(text)

    if length <= max_chars:
        return Passage(text, 0, length)

    start = min(
        max(0, match_start - max_chars // 3),
        length - max_chars,
    )
    end = start + max_chars

    if preserve_code:
        # Prefer complete code lines whenever possible.
        first_newline = text.find(
            "\n", start, min(end, match_start)
        )

        if (
            start
            and first_newline != -1
            and first_newline - start <= 30
        ):
            start = first_newline + 1

        last_newline = text.rfind(
            "\n", match_start, end
        )

        if (
            end < length
            and last_newline > start
            and end - last_newline <= 30
        ):
            end = last_newline

        while start < end and text[start] == "\n":
            start += 1

        while end > start and text[end - 1] == "\n":
            end -= 1

    else:
        # Avoid cutting words at passage boundaries.
        if (
            start
            and text[start - 1].isalnum()
            and text[start].isalnum()
        ):
            boundary = text.find(
                " ",
                start,
                min(start + 24, match_start),
            )

            if boundary >= 0:
                start = boundary + 1

        if (
            end < length
            and text[end - 1].isalnum()
            and text[end].isalnum()
        ):
            boundary = text.rfind(
                " ",
                max(match_start, end - 24),
                end,
            )

            if boundary >= 0:
                end = boundary

        while start < end and text[start].isspace():
            start += 1

        while end > start and text[end - 1].isspace():
            end -= 1

    # Boundary adjustments must never exceed the requested character budget.
    if end - start > max_chars:
        end = start + max_chars

    return Passage(
        text=text[start:end],
        start=start,
        end=end,
    )


def _candidates(
    text: str,
    pattern: re.Pattern[str] | None,
    max_chars: int,
    max_candidates: int,
    preserve_code: bool,
) -> tuple[Passage, ...]:
    """Select candidate windows from across the source document."""
    if not text:
        return ()

    if len(text) <= max_chars:
        return (Passage(text, 0, len(text)),)

    if pattern is None:
        excerpt = text[:max_chars].rstrip()
        return (Passage(excerpt, 0, len(excerpt)),)

    # Sample matches across eight regions per query term.
    # This prevents repeated terms at the start of a long
    # document from consuming every candidate slot.
    positions: dict[tuple[str, int], int] = {}

    for match in pattern.finditer(text):
        bucket = min(
            7,
            match.start() * 8 // len(text),
        )

        key = (match.lastgroup or "", bucket)
        positions.setdefault(key, match.start())

    # Deduplicate identical passage windows.
    by_start: dict[tuple[int, int], Passage] = {}

    for offset in positions.values():
        passage = _window(
            text,
            offset,
            max_chars,
            preserve_code=preserve_code,
        )

        by_start[(passage.start, passage.end)] = passage

    # Highest relevance first; earlier passages break ties.
    ranked = sorted(
        by_start.values(),
        key=lambda passage: (
            -_score_with_pattern(passage.text, pattern),
            passage.start,
        ),
    )

    return tuple(ranked[:max_candidates])


def find_candidate_passages(
    text: str,
    query_terms: Iterable[str],
    *,
    max_chars: int = 200,
    max_candidates: int = 64,
    preserve_code: bool = False,
) -> tuple[Passage, ...]:
    """Return candidate passages ordered by relevance."""
    _positive_integer(max_chars, "max_chars")
    _positive_integer(max_candidates, "max_candidates")

    normalized_text = normalize_snippet_text(
        text,
        preserve_code=preserve_code,
    )

    pattern = _pattern(
        _normalize_terms(query_terms)
    )

    return _candidates(
        normalized_text,
        pattern,
        max_chars,
        max_candidates,
        preserve_code,
    )


def generate_snippet(
    text: str,
    query_terms: Iterable[str],
    *,
    description: str | None = None,
    max_chars: int = 200,
    preserve_code: bool = False,
) -> Snippet:
    """Generate the best query-relevant snippet.

    Uses a description or the beginning of the document if
    no query terms are found.

    Highlight offsets refer to the final Snippet.text.
    Treat the returned content as plain text, never HTML.
    """
    _positive_integer(max_chars, "max_chars")

    normalized_text = normalize_snippet_text(
        text,
        preserve_code=preserve_code,
    )

    if description is not None and not isinstance(
        description, str
    ):
        raise TypeError(
            "description must be a string or None"
        )

    terms = _normalize_terms(query_terms)
    pattern = _pattern(terms)

    candidates = _candidates(
        normalized_text,
        pattern,
        max_chars,
        64,
        preserve_code,
    )

    best = candidates[0] if candidates else None

    if (
        best is not None
        and _score_with_pattern(best.text, pattern) > 0
    ):
        source = normalized_text
        chosen = best
    else:
        fallback = normalize_snippet_text(
            description or "",
            preserve_code=preserve_code,
        )

        source = fallback or normalized_text
        end = min(max_chars, len(source))

        chosen = Passage(
            text=source[:end],
            start=0,
            end=end,
        )

    highlights = (
        ()
        if pattern is None
        else tuple(
            (match.start(), match.end())
            for match in pattern.finditer(chosen.text)
        )
    )

    return Snippet(
        text=chosen.text,
        highlights=highlights,
        truncated_start=chosen.start > 0,
        truncated_end=chosen.end < len(source),
    )
