# Developer's Eye: Indexer Analyzer

**Module:** `crawler/src/indexer/analyzer.py`  
**Input:** `IndexDocument`  
**Output:** `AnalyzedDocument`  
**Responsibility:** Decide *which fields get indexed, with what importance and configuration*.

## Pipeline

```text
selector.py           selects documents that need an index
    ↓ IndexCandidate
builder.py            fetches, validates, normalizes + hashes content
    ↓ IndexDocument
analyzer.py           divides content into weighted prose/code fields
    ↓ AnalyzedDocument
vector.py             constructs weighted PostgreSQL TSVECTOR expressions
    ↓ vectors
writer.py             rechecks freshness and persists the search index
```

## What the analyzer does

1. Receives a validated `IndexDocument` from the builder.
2. Joins structured metadata like `tags`, `headings` and `code_blocks` with `\n\n` separators.
3. Removes blank fields and rejects PostgreSQL-incompatible NUL characters.
4. Assigns each field a PostgreSQL FTS weight: `A > B > C > D`.
5. Separates prose and code into two vector inputs, using the configured search dictionaries.
6. Returns immutable objects. **No SQL, database I/O, stemming, tokenization, or vectors are built here.**

## Fields and weights

| Prose (`text_fields`) | Weight | Code (`code_fields`) | Weight |
|---|---|---|---|
| Title | A | Tags | A |
| Tags | A | Title | A |
| Headings | B | Code blocks | B |
| Description | B | Headings | B |
| Body | C | Canonical URL | D |

The `text_search_config` defaults to `english`; the `code_search_config` defaults to `simple`. Both values come from `IndexerConfig`, not hardcoded analyzer logic. `simple` skips English stemming, **but still tokenizes and does not preserve exact code punctuation or identifier boundaries**.

## Functions

### `AnalyzedField`

Immutable dataclass holding one field: `name`, `text`, `weight`, `search_config`.

### `AnalyzedDocument`

Immutable dataclass holding `document_id`, `source_id`, `source_updated_at`, `text_fields` and `code_fields`.

### `_join_items(items, *, name, document_id)`

Validates tuples of strings, skips empty items, and joins remaining items with a blank line. It keeps code indentation intact.

### `_field(*, name, text, weight, search_config, document_id)`

Validates one field, rejects NUL (`\x00`), and returns `None` for blank text. Otherwise returns an `AnalyzedField`.

### `analyze_index_document(document, *, config)`

Main public function. Arranges the fields and weights, removes blank fields, checks for empty searchable content, and returns an `AnalyzedDocument`.

## Example

Input from `builder.py`:

```python
# Selected fields of an IndexDocument
title = "Python Async Tutorial"
body = "Learn asynchronous Python with async and await"
tags = ("Python", "asyncio")
code_blocks = ("async def main():\n    await run()",)
```

Analyzer output, simplified:

```text
text_fields:
  title        weight A   english
  tags         weight A   english
  body         weight C   english

code_fields:
  tags         weight A   simple
  title        weight A   simple
  code_blocks  weight B   simple
  canonical_url weight D  simple
```

Next, `vector.py` can construct expressions like:

```sql
setweight(to_tsvector('english', :title), 'A') ||
setweight(to_tsvector('english', :body), 'C')
```

This is *illustrative SQL*, not emitted by `analyzer.py`. Real `vector.py` must safely bind text and validate/whitelist search configurations before using them as PostgreSQL `regconfig` identifiers.

## Architectural rules

- **Builder owns content normalization and index hashes.** Do not independently change normalization in the analyzer or a hash may fail to represent the actual indexed input.
- **Analyzer owns fields and weights.** Changing mappings or configurations must increment `INDEXER_INDEX_VERSION` so old index rows get rebuilt.
- **Vector owns `to_tsvector`, `setweight` and vector combination.** `weight` values affect PostgreSQL FTS ranking. They do not constitute BM25 by themselves.
- **Writer owns persistence and race safety.** After the builder/analyzer run, the source document can still change. Recheck the source snapshot within the writer transaction.
- **Tokenizer limitations:** PostgreSQL `simple` search alone won't support precise searches for `snake_case`, `foo.bar`, `C++` or mixed symbol-heavy expressions. Consider trigram/exact identifier support in a later search stage.

## Tests

Run from `crawler/`:

```bash
poetry run pytest tests/indexer/test_analyzer.py -q
poetry run pytest tests/indexer/test_builder.py -q
poetry run pytest tests/indexer/test_selector.py -q
```

The builder and analyzer tests don't need PostgreSQL. The selector tests use a **disposable test database** because they must check actual SQL selection logic. They skip if `TEST_DATABASE_URL` is unset. Set an async driver URL, for example `postgresql+asyncpg://USER:PASSWORD@localhost:5432/developers_eye_test`, in the test environment to enable them. Never point test setup at production.

The selector integration fixture creates its own schema in one PostgreSQL transaction and rolls back everything afterward. It generates minimal test tables from the mapped SQLAlchemy column types, avoiding dependencies on other crawler tables.

## Known design tradeoffs

- A field such as `tags` or `title` is duplicated across prose and code vectors by design.
- `headings`, `tags`, and `code_blocks` preserve their relative order. Reordering them changes hash input in the builder.
- Empty optional fields are omitted, not represented as blank `AnalyzedField`s.
- Changing weights should invalidate the index by bumping `index_version`; the content hash alone is not sufficient.
