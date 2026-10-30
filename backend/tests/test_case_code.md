# Developer's Eye: `retrieval/code.py` Test Cases

## Contract

- **Purpose:** Retrieve code-relevant *document IDs* from the already populated `search_index.code_vector`.
- **Input:** An existing SQLAlchemy `AsyncSession`, query string, `limit` (1 to 100), `offset` (0 to 10,000).
- **Output:** `list[CodeRetrievalHit]` with `document_id: int` and `score: float`.
- **Query mode:** PostgreSQL `plainto_tsquery('simple', ...)`, which uses AND between lexemes.
- **Rank:** PostgreSQL `ts_rank_cd(..., 32)`. This is a retrieval score, **not BM25**.
- **Selection:** `code_vector @@ tsquery`. This is compatible with a GIN index on `code_vector`.
- **Order:** descending retrieval score, ascending document ID for deterministic ties.
- **No ownership:** The function does not open, commit, or close the caller's database session.
- **No joins:** It must not read from `document` or perform snippet generation.

## Automated test matrix

| ID | Test | Input / Setup | Expected result |
|---|---|---|---|
| C01 | Maps DB results | Two rows returned | Two typed hits, values preserved |
| C02 | Normalizes whitespace | Tabs/newlines around terms | Single-spaced query sent as bind parameter |
| C03 | Defaults | `search_code(session, 'include_router')` | `limit=50`, `offset=0` |
| C04 | Empty query | `''` | `[]`, no DB call |
| C05 | Whitespace-only query | spaces, tabs, newline, em space | `[]`, no DB call |
| C06 | Invalid query type | `None`, `int`, `list`, `dict` | `TypeError`, no DB call |
| C07 | Query maximum | 512 ASCII characters | Accepted |
| C08 | Query too long | 513 ASCII characters | `ValueError`, no DB call |
| C09 | ASCII controls | `\x00`, `\x01`, `\x7f` | `ValueError`, no DB call |
| C10 | Pagination validation | 0/negative/oversized/non-integer/bool | `ValueError`, no DB call |
| C11 | Boundary pagination | limit 100, offset 10,000 | Accepted |
| C12 | SQL injection defense | `x'); DROP TABLE ...` | Query remains bound, never interpolated |
| C13 | Unicode query | `解析 asyncio` | Passed to PostgreSQL intact |
| C14 | No matches | Empty DB result | `[]` |
| C15 | DB exception | `.execute` raises | Exception propagates |
| C16 | No ID rewriting | Document 4 returned | Document 4 preserved |
| C17 | SQL design | Check generated SQL | Uses `code_vector`, `simple`, `@@`, `ts_rank_cd`, deterministic ordering |
| C18 | PostgreSQL integration (optional) | Temporary search_index with 3 entries | Only correctly matching IDs returned; score positive; offset enforced |

## Manual PostgreSQL checks

**Prerequisite:** The existing indexer produced the `code_vector` column using the `simple` text-search configuration. Check that `document_id` is an integer-compatible key. Replace identifiers in the implementation if your actual model differs.

```sql
-- Confirm indexed data exists.
SELECT document_id, left(code_vector::text, 160) AS preview
FROM search_index
WHERE code_vector IS NOT NULL
LIMIT 5;

-- Confirm an index suitable for code-vector search exists.
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'search_index'
ORDER BY indexname;

-- Inspect what 'simple' actually tokenizes.
SELECT to_tsvector('simple', 'FastAPI APIRouter include_router std::vector');
SELECT plainto_tsquery('simple', 'FastAPI APIRouter include_router');
```

For production query-plan assessment, run `EXPLAIN (ANALYZE, BUFFERS)` against a populated database and compare latency at representative index sizes. PostgreSQL may reasonably choose a sequential scan on a small test table even if a GIN index exists.

## Running tests (Windows PowerShell, from `backend/`)

```powershell
poetry run pytest src/backend/tests/unit/test_code.py -v
```

Run from the backend project root, with the `src/` package path enabled (for example through your Poetry configuration or `PYTHONPATH=src`).

**Optional real PostgreSQL run:** Set `TEST_DATABASE_URL` to a **dedicated test database** URL using the `postgresql+asyncpg://` driver and re-run the same command. Without the environment variable, only the integration case is skipped.

## Known v1 limitations and follow-up tests

1. **AND semantics:** A query with multiple lexemes matches only indexed vectors containing all of them. OR/weighted recall belongs in a later retrieval policy.
2. **Punctuation:** PostgreSQL text-search parsing is not a byte-exact code-symbol index. Expressions such as `std::vector`, `foo.bar()`, `C++`, and `list[i]` require separate exact-identifier matching if punctuation distinctions matter.
3. **Rank:** `ts_rank_cd` is a preliminary rank. BM25 must be implemented and tested separately in the final ranker. Do not compare `ts_rank_cd` directly across heterogeneous retrievers without calibration.
4. **Performance:** Production tests should verify representative candidate counts, long-tail query latency, SQL plans, and GIN index behavior. Mocked unit tests do not measure these.
5. **Deletion consistency:** If indexer deletes a document from `search_index`, this retriever should no longer return it. That behavior belongs in database-backed indexer/retriever integration tests.
6. **Pagination stability:** Sorting by score and ID is deterministic for a fixed index snapshot, but results can shift across separate requests if the index changes. Cursor/snapshot pagination is a future concern.
