# Snippet Engine

**Module:** `backend.search.snippets`  
**Implementation:** `backend/src/backend/search/snippets.py`  
**Tests:** `backend/tests/unit/test_snippets.py`

## Purpose

The snippet engine extracts a short, query-relevant passage from a document to display beneath its search-result title. It also returns exact highlight ranges so the frontend can emphasize matching terms without accepting generated HTML.

This module is pure Python. It does **not** query PostgreSQL, load documents, rank whole documents, select retrieval modes, or render HTML. Call it only after retrieval, deduplication, ranking, and pagination have selected the final result page.

## Pipeline placement

```text
User query
  -> query analyzer (validates/normalizes raw query)
  -> search planner + router
  -> text/code retrieval
  -> merge, deduplicate, rank, paginate
  -> batch-load body/description for the final page
  -> generate_snippet(...) for each selected document
  -> API (text + highlights + truncation flags)
  -> frontend rendering
```

## Public API

| Name | Inputs | Output | Purpose |
| --- | --- | --- | --- |
| `normalize_snippet_text` | `text`, `preserve_code=False` | `str` | NFC-normalize and clean text; optionally preserve line breaks and indentation |
| `find_highlight_spans` | `text`, `query_terms` | `tuple[(start, end), ...]` | Return case-insensitive, non-overlapping literal-match ranges |
| `score_passage` | `passage`, `query_terms` | `int` | Score distinct query-term coverage and capped repetitions |
| `find_candidate_passages` | `text`, `query_terms`, `max_chars=200`, `max_candidates=64`, `preserve_code=False` | `tuple[Passage, ...]` | Return sampled candidate windows sorted by score |
| `generate_snippet` | `text`, `query_terms`, `description=None`, `max_chars=200`, `preserve_code=False` | `Snippet` | Build one final result preview |

`query_terms` must be an iterable of individual strings, not a single query string. Terms may include spaces if an upstream parser explicitly treats a phrase as one term.

### Output types

`Snippet` (frozen and slotted dataclass):

- `text: str`: plain, human-readable excerpt; **not** escaped or trusted HTML.
- `highlights: tuple[tuple[int, int], ...]`: sorted, non-overlapping `(start, end)` offsets into `Snippet.text`. `end` is exclusive.
- `truncated_start: bool`: whether content before the selected excerpt was omitted.
- `truncated_end: bool`: whether content after the selected excerpt was omitted.

`Passage` (frozen and slotted dataclass):

- `text: str`: the selected text window.
- `start: int`, `end: int`: offsets into the **normalized document text**, not the original raw document.

## Usage

```python
from backend.search.snippets import generate_snippet

body = (
    "FastAPI is a Python web framework. "
    "It supports async database connections for concurrent requests."
)

result = generate_snippet(
    text=body,
    query_terms=("fastapi", "async", "database"),
    description="FastAPI documentation",
    max_chars=100,
)

print(result.text)
print(result.highlights)
print(result.truncated_start, result.truncated_end)
```

The caller supplies **normalized, meaningful query terms**. As a short-term MVP, splitting the existing query-analyzer output on whitespace can work for simple keyword queries, but it mishandles quoted phrases, programming symbols, and operators.

## Internal execution flow

### 1. Normalize text

`normalize_snippet_text(text, preserve_code=False)` first applies Unicode NFC normalization and canonicalizes CRLF/CR newlines to LF.

- **Prose mode:** collapses all whitespace runs into one space and strips edges.
- **Code mode:** keeps internal newlines, spaces, and indentation; removes surrounding newline characters. Whitespace-only input becomes empty.

### 2. Normalize and validate terms

Private `_normalize_terms()`:

- Validates that the input is an iterable of strings rather than a single string.
- NFC-normalizes each term, ignores blank terms, and deduplicates terms case-insensitively.
- Enforces at most `MAX_QUERY_TERMS = 32` unique terms and `MAX_TERM_CHARS = 128` characters per term.

### 3. Compile a match pattern

Private `_pattern()` compiles literal, case-insensitive regular expressions for the query terms:

- `re.escape()` ensures punctuation is interpreted literally, not as executable regex syntax.
- Longer terms are matched before shorter overlapping terms.
- Word-boundary checks on alphanumeric/underscore edges avoid matching `go` inside `google`.

This is **literal matching**, not stemming, semantic matching, language detection, or fuzzy search. A stemmed lexeme such as `tutori` will not automatically highlight `tutorial`.

### 4. Find candidate passages

Private `_candidates()` scans match positions and divides the document into eight regions. For each term and region, it keeps the earliest match. `_window()` extracts up to `max_chars` characters around those matches, trimming at nearby whitespace boundaries for prose and favoring complete lines for code.

Candidate windows are deduplicated and ranked. `find_candidate_passages()` returns the top `max_candidates`, default 64.

**Approximation:** Sampling one match per term per region means this engine does not guarantee finding the mathematically optimal passage. It trades exhaustive window enumeration for bounded candidates.

### 5. Score passages

`score_passage()` uses:

```text
score = 4 × distinct_query_terms_matched
      + sum(min(term_occurrences, 3) for each matched term)
```

Example: `"python async"` with terms `("python", "async")` scores `4*2 + 1 + 1 = 10`. Repeating `python` ten times without `async` scores `4*1 + 3 = 7`.

The scoring encourages query-term coverage and caps the reward from repeated occurrences. These scores are **only for passage selection**, not whole-document relevance ranking.

### 6. Build the final snippet

`generate_snippet()`:

1. Normalizes text and query terms.
2. Retrieves ranked candidate windows.
3. If the best window contains a query-term match, uses it.
4. Otherwise, falls back to the normalized `description` if nonempty, or the prefix of the normalized body.
5. Finds match spans in the **final excerpt**, ensuring offsets correspond to returned text.
6. Returns a `Snippet` with truncation flags.

If body and description are empty, the result has empty text, no highlights, and both truncation flags false.

## Input validation and edge cases

- `max_chars` and `max_candidates` must be positive actual integers; `True` and floating-point values are rejected.
- Non-string body, non-string terms, and invalid description types are rejected.
- No matching terms: falls back to description or document prefix.
- No query terms: likewise uses the fallback.
- Snippets never exceed `max_chars` code points, although the selected text can be shorter because of word/line trimming.
- `find_candidate_passages()` returns `()` on a long nonmatching document; fallback selection is done by `generate_snippet()`.
- Highlight ranges use **Python Unicode code-point offsets**. JavaScript strings use UTF-16 code units, so use `Array.from(text)`/code-point-aware slicing or convert offsets when rendering text containing emoji or other astral characters.

## Security

Snippet content originates from untrusted crawled pages. The engine returns **plain text** and positions only. It does not escape text or emit markup. The frontend **must** render text via React text nodes (or equivalent safe escaping), not `dangerouslySetInnerHTML`. A source containing `<script>...</script>` remains a literal text string.

## Performance and operational guidance

- The engine processes the normalized document body in memory and scans it to find regex matches. It is not a streaming implementation.
- Candidate sampling bounds the number of stored match positions roughly by `8 × unique_query_terms`, but it still scans the input text and normalizes the full body.
- Do not call it for every retrieved candidate. Rank and paginate first, batch-load bodies/descriptions for the displayed results, then generate snippets.
- Extremely large bodies may require upstream content-size limits or a different passage-generation strategy.
- The code contains no database writes, global mutable state, or network calls.

## Integration contract

The current `SearchResult` data contract contains `snippet: str`. Pass `generate_snippet(...).text` into that field. If you want frontend highlighting and ellipses, extend the API schema to send `highlights`, `truncated_start`, and `truncated_end` alongside the text.

Before integration, make sure the service's query-term extraction matches how your PostgreSQL FTS query is interpreted. A naive `.split()` is **not** a full parser for quoted phrases or Boolean operators.

## Running tests

From the `backend` directory, with your backend environment active:

```powershell
python -m pytest tests/unit/test_snippets.py -v
```

The test suite covers normalization, matching, ranking, candidate windows, fallbacks, code indentation, Unicode, input validation, and output invariants. It does not measure performance under production-scale document sizes or test the Next.js highlighting implementation.

## Known limitations / future improvements

- Approximate eight-region candidate sampling can miss a better passage in the same region.
- Literal matching does not use PostgreSQL stemming, fuzzy correction, synonyms, or semantic similarity.
- Code and prose share a simple relevance scorer; neither is aware of AST/syntax structure.
- `max_chars` counts Python code points, not grapheme clusters or visible display width.
- Fallback prefixes can cut words; better sentence-boundary fallback may be added.
- Add benchmarks before claiming production-scale latency or throughput.

Keep engineering trade-offs, rejected algorithms, and postmortems in `tech_docs/`; this file documents the implementation's behavior and API.
