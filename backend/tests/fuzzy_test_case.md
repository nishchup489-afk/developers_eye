# Developer's Eye: Fuzzy Retrieval Test Cases

**Module under test:** `backend.search.retrieval.fuzzy.get_fuzzy_search`  
**Test module:** `backend/src/backend/tests/integration/test_fuzzy.py`  
**Status:** **Not executed against your database.** All expected results below are test assertions, not reported passes.

## Expected v1 behavior

```python
async def get_fuzzy_search(
    query: str,
    session: AsyncSession,
    limit: int = 20,
) -> list[dict[str, int | float]]:
    ...
```

Each returned row is `{"document_id": int, "fuzzy_score": float}`. Search the **document title** with PostgreSQL `pg_trgm` word similarity, rank by score descending and document ID ascending, and return no more than `limit` results. For these tests, the configured `pg_trgm.word_similarity_threshold` is `0.6`.

This is a **proposed contract** for `fuzzy.py`. If your eventual design intentionally uses a different function name, schema, return fields, or matching algorithm, update the tests and document the change rather than modifying production code blindly.

## Test cases

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| FZ-01 | `test_exact_title_match_has_highest_score` | `Python Async Tutorial` | Duplicate exact-title documents 101 and 105 appear first; both score 1.0; ID breaks tie | Not run |
| FZ-02 | `test_prefix_typo_finds_fastapi_titles` | `fastap` | Finds FastAPI documents 102 and 110 at word-similarity threshold 0.6 | Not run |
| FZ-03 | `test_extra_character_typo_finds_python` | `pythonn` | Finds document 101 containing Python | Not run |
| FZ-04 | `test_relevant_title_outscores_less_relevant_title` | `FastAPI Authentication` | Exact-title document 110 ranks first with score 1.0 | Not run |
| FZ-05 | `test_unrelated_query_returns_no_results` | `zzzxqvv` | Returns `[]` | Not run |
| FZ-06 | `test_case_insensitive_matching` | `FASTAPI` vs `fastapi` | Identical IDs, order and scores | Not run |
| FZ-07 | `test_trims_outer_whitespace` | `  fastapi  ` vs `fastapi` | Identical results | Not run |
| FZ-08 | `test_limit_one_and_stable_tie_break` | Exact-title search, `limit=1` | Returns only document 101 | Not run |
| FZ-09 | `test_limit_is_respected` | `python`, `limit=2` | Returns exactly two matching documents | Not run |
| FZ-10 | `test_search_never_returns_duplicate_documents` | `python`, `limit=100` | Each document ID occurs once; consistent schema, score range and sorting | Not run |
| FZ-11 | `test_no_table_mutation_from_user_input` | SQL-injection-shaped query | Original 12 temporary documents remain intact | Not run |
| FZ-12 | `test_blank_query_skips_database` | `""`, spaces, tabs/newlines | Returns `[]` without calling the DB | Not run |
| FZ-13 | `test_non_string_query_rejected_before_database` | `None`, `12`, `[]`, `{}` | Raises `TypeError` without calling the DB | Not run |
| FZ-14 | `test_invalid_limit_rejected_before_database` | `0`, `-1`, `101`, `True`, `3.5`, `"20"`, `None` | Raises `ValueError` without calling the DB | Not run |
| FZ-15 | `test_database_error_propagates_to_caller` | Mocked DB raises `RuntimeError` | Error propagates; no fabricated empty results | Not run |

**Test count:** 15 test functions, **26 collected parameterized cases** (11 ordinary DB tests + 1 DB-error test + 3 blank cases + 4 invalid-query cases + 7 invalid-limit cases).

## Test data and isolation

The PostgreSQL fixture populates a **temporary** table whose name is derived from `Document.__table__`; this shadows the real unqualified ORM table only for the test connection. The table contains 12 invented document titles, including two identical titles to verify tie-breaking. The test creates a temporary GIN trigram index, then drops everything via transaction rollback.

**Preconditions:**

1. `Document` is exported by `backend.models` and has `title` and one integer primary-key column.
2. `get_fuzzy_search` exists in `backend.search.retrieval.fuzzy` with the return contract above.
3. `TEST_DATABASE_URL` points to a dedicated PostgreSQL database **named exactly `developers_eye_test`**. The test fixture refuses a different database name.
4. `pg_trgm` is installed in the test database (`CREATE EXTENSION IF NOT EXISTS pg_trgm;`).
5. The database role can create temporary tables. `pytest`, `pytest-asyncio`, `SQLAlchemy`, and `asyncpg` are installed.

## Run on Windows PowerShell

From `developers-eye/backend/`:

```powershell
$env:PYTHONPATH = "src"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://YOUR_USERNAME:YOUR_PASSWORD@localhost:5432/developers_eye_test"
poetry run pytest src/backend/tests/integration/test_fuzzy.py -v --tb=short
```

Replace credentials with your own; never commit credentials or paste them into public logs. If the password contains reserved URL characters, URL-encode it.

To install `pg_trgm` in your **test** database, connect to `developers_eye_test` with psql and run:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## Scope and limitations

- The tests cover **title-based, word-similarity fuzzy candidate retrieval**. They do **not** test token-by-token autocorrection, whole-document fuzzy search, `pythno` transposition recall, BM25, query routing, snippets, or HTTP pagination.
- The fixture installs the same kind of temporary GIN trigram index as production would, but **does not prove the PostgreSQL planner selects that index** on a tiny 12-row table. Benchmark production-sized data with `EXPLAIN (ANALYZE, BUFFERS)` separately.
- Fuzzy score values depend on the chosen similarity function and threshold; only exact-title matches are asserted to score precisely 1.0.
- If `Document` uses a schema-qualified table or UUID primary key, the fixture will fail with a clear message; adapt the fixture to that actual schema before relying on the results.
