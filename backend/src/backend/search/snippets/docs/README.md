# Snippet engine

The snippet engine selects query-relevant excerpts from normalized document text. It does not access the database or render HTML.

## Pipeline

1. `validation.py` normalizes Unicode (NFC), whitespace and query terms, validates limits, and builds escaped case-insensitive regex alternatives.
2. `ranking.py` scores a passage using four points per distinct matched term plus up to three occurrences per term. It also exposes end-exclusive highlight offsets.
3. `snippets.py` samples the first match for each term across eight document regions, constructs bounded windows, deduplicates them, and sorts candidates by descending relevance, breaking ties by earliest offset.
4. `generate_snippet` selects the highest-ranked candidate. If no candidate matches, it uses the description when nonempty, otherwise the document prefix.

## Public API

`generate_snippet(text, query_terms, description=None, max_chars=200, preserve_code=False)` returns `Snippet(text, highlights, truncated_start, truncated_end)`. Highlights are zero-based, end-exclusive character spans into **the returned snippet**, not the original document. Truncation flags indicate omitted content before or after the chosen excerpt.

`find_candidate_passages(text, query_terms, max_chars=200, max_candidates=64, preserve_code=False)` returns `Passage(text, start, end)` values with offsets into normalized source text.

`find_highlight_spans(text, query_terms)` and `score_passage(passage, query_terms)` expose matching and scoring independently.

`preserve_code=True` keeps newlines and indentation, preferring line boundaries. Both modes enforce `len(snippet.text) <= max_chars`. Prose mode collapses whitespace. Query terms are limited to 32 distinct terms of up to 128 characters each. `max_chars` and `max_candidates` must be positive integers.

## Safety and limitations

Treat snippet text as untrusted plain text. Escape it when rendering HTML; highlight spans are data, not markup. Regex query terms are escaped, not executed as regex syntax. Candidate sampling is bounded by term-region combinations, but regex matching still scans the document. The algorithm is heuristic and does not guarantee globally optimal relevance.

## Tests

From `backend/`, run `poetry run pytest src/backend/search/snippets/tests -q` (or `poetry run pytest -q` for the complete backend suite).
