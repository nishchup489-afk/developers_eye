
"""Public API for Developer's Eye snippet engine."""

from .types import (
    MAX_QUERY_TERMS,
    MAX_TERM_CHARS,
    Passage,
    Snippet,
)

from .validation import normalize_snippet_text

from .ranking import (
    find_highlight_spans,
    score_passage,
)

from .snippets import (
    find_candidate_passages,
    generate_snippet,
)


__all__ = [
    "MAX_QUERY_TERMS",
    "MAX_TERM_CHARS",
    "Passage",
    "Snippet",
    "normalize_snippet_text",
    "find_highlight_spans",
    "score_passage",
    "find_candidate_passages",
    "generate_snippet",
]
