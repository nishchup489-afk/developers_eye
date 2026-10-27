# Developer's Eye: `vector.py`

## Purpose

`vector.py` turns `AnalyzedDocument` into **two typed SQLAlchemy `TSVECTOR` SQL expressions** for PostgreSQL full-text search. It **does not** convert text to lexemes in Python, run SQL, persist anything, or create embeddings.

```text
selector.py → IndexCandidate
builder.py  → IndexDocument (+ indexed_hash via calculate_index_hash)
analyzer.py → AnalyzedDocument (weighted fields)
vector.py   → SearchVectors (SQL expressions)
writer.py   → Executes SQL after transactional freshness validation
PostgreSQL  → Stores TSVECTOR values; GIN indexes accelerate matching
```

## Input contract

`AnalyzedDocument` includes `document_id`, `source_id`, `source_updated_at`, and two tuples of `AnalyzedField` objects:

| Group | Typical fields | Default search configuration |
|---|---|---|
| `text_fields` | Title (A), tags (A), headings (B), description (B), body (C) | `english` |
| `code_fields` | Tags (A), title (A), code blocks (B), headings (B), canonical URL (D) | `simple` |

The analyzer assigns weights; the vector module applies them. Fields in each group must match the corresponding `IndexerConfig` configuration exactly. Configuration names are validated for identifier syntax and passed as bound values; PostgreSQL determines whether those configurations actually exist at execution time.

## Output contract

`SearchVectors` is a frozen dataclass with the original document ID, source ID, revision timestamp and two `ColumnElement` expressions:

- `text_vector`: weighted `TSVECTOR` SQL expression for prose-oriented retrieval.
- `code_vector`: weighted `TSVECTOR` SQL expression for technical/code-oriented retrieval.

**These are not evaluated vectors.** The writer must embed them into a PostgreSQL statement and execute that statement.

## Function reference

### `_empty_vector()`

Returns a typed SQL expression equivalent to `CAST('' AS TSVECTOR)`. Empty input groups and blank individual fields use this representation rather than returning `None`.

### `_validate_field(field)`

Checks that the input is an `AnalyzedField`, that the text is a string without NUL (`\x00`), the weight is exactly `A`, `B`, `C`, or `D`, and the search configuration follows the allowed SQL identifier syntax (up to 127 characters).

A valid-looking name is **not** a guarantee that the configuration exists in the target database.

### `build_field_vector(field)`

1. Validate the field.
2. Return `_empty_vector()` for whitespace-only text.
3. Bind the text using `literal(..., type_=Text())`.
4. Bind the configuration string and cast it to PostgreSQL `REGCONFIG`.
5. Create `to_tsvector(config, text)` with `TSVECTOR` return typing.
6. Apply `setweight(vector, 'A' | 'B' | 'C' | 'D')` using only predefined literals.

Example **equivalent SQL** (not necessarily the exact compiled parameter names):

```sql
setweight(
    to_tsvector(CAST(:config AS REGCONFIG), :title),
    'A'
)
```

`literal_column()` is safe for the weight here because it can only contain one of four hard-coded SQL literals. Never construct literal SQL fragments from document data.

### `combine_vectors(fields)`

Takes a tuple of analyzed fields and builds each weighted field expression. It uses PostgreSQL `||` to concatenate them in source order. For three fields it constructs the equivalent of:

```sql
weighted_title || weighted_headings || weighted_body
```

`||` on `TSVECTOR` concatenates lexemes and adjusts positions of the right-hand vector; it is not Boolean OR. With no fields, the function creates an empty vector expression.

### `build_search_vectors(document, *, config)`

Validates argument types, positive integer IDs (rejects booleans), datetime revision, tuple field groups, and configuration agreement. Calls `combine_vectors()` separately for text and code and returns `SearchVectors`.

This function does not compute `indexed_hash`. The builder's `calculate_index_hash()` does that earlier in the indexing workflow.

## Example

```python
from indexer.analyzer import analyze_index_document
from indexer.vector import build_search_vectors

analyzed = analyze_index_document(index_document, config=config)
vectors = build_search_vectors(analyzed, config=config)

# Expressions, not PostgreSQL results:
text_expr = vectors.text_vector
code_expr = vectors.code_vector
```

A single title field such as `Python Async Tutorial` with weight A and `english` config generates an expression conceptually equivalent to:

```sql
setweight(to_tsvector('english', 'Python Async Tutorial'), 'A')
```

When executed in PostgreSQL, this might yield `'async':2A 'python':1A 'tutori':3A`.

## Tests

Place the test file at `crawler/src/indexer/tests/test_vector.py`. This project already has shared fixtures in `crawler/src/indexer/tests/conftest.py` (`config`, `make_index_document`). Do not create another `tests/indexer/` directory.

From the `crawler/` directory:

```powershell
poetry run pytest src/indexer/tests/test_vector.py -v
poetry run pytest src/indexer/tests -v
```

The test file covers typed SQL generation, parameter binding (including SQL-injection-looking input), valid weights, invalid text/configuration, empty vectors, field order, deterministic compilation, dataclass metadata, analyzer integration, and argument validation.

The optional PostgreSQL execution test is skipped unless `TEST_DATABASE_URL` is set to an isolated PostgreSQL connection string using the SQLAlchemy `asyncpg` driver:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/developers_eye_test"
poetry run pytest src/indexer/tests/test_vector.py -v
```

Unlike the SQL-compilation tests, this test checks actual PostgreSQL lexeme normalization and weights. It performs a `SELECT` only and never modifies tables. Use a **test** database URL.

## Safety and correctness boundaries

- Document text and configuration values are bound parameters. Hard-coded weights are the only literal SQL fragments.
- No SQL executes before the writer uses these expressions.
- The writer must revalidate the source revision inside a concurrency-safe transaction prior to committing the index.
- The database schema must support separate text and code vectors; create GIN indexes on each vector column if queries use them.
- PostgreSQL `simple` does not preserve punctuation or provide exact code identifier search; it merely avoids English stemming. Consider supplemental trigram/exact-identifier search for code-specific behavior.
- Change `INDEXER_INDEX_VERSION` when the analyzer weights/configurations or vector semantics change so stale indices can be rebuilt.
- `frozen=True` prevents rebinding `SearchVectors` dataclass fields, but does not recursively freeze internal SQLAlchemy expression objects.
