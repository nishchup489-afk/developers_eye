# Developer's Eye: Backend Test Cases

One document for every backend test case: the tests written in `backend/tests/`, plus the retrieval suites (FTS, code, fuzzy) whose test modules live in `backend/src/backend/tests/`.

## Contents

1. [Inventory](#inventory)
2. [Package boundary](#package-boundary)
3. [Ranking orchestrator](#ranking-orchestrator)
4. [Full-text search (FTS)](#full-text-search-fts)
5. [Code retrieval](#code-retrieval)
6. [Fuzzy retrieval](#fuzzy-retrieval)
7. [Running tests](#running-tests)
8. [Not covered yet](#not-covered-yet)

## Inventory

| Suite | Test file | Functions | Collected cases | Status |
|---|---|---|---|---|
| Package boundary | `backend/tests/test_package_boundary.py` | 1 | 1 | Not run |
| Ranking orchestrator | `backend/tests/unit/test_ranking_orchestrator.py` | 14 | 17 | Passed (commit `b818adc`) |
| Full-text search | `backend/src/backend/tests/integration/test_fts.py` | 14 | 25 | Passed (commit `563b83d`) |
| Code retrieval | `backend/src/backend/tests/unit/test_code.py` | 18 matrix rows | See section | Not recorded |
| Fuzzy retrieval | `backend/src/backend/tests/integration/test_fuzzy.py` | 15 | 26 | Not run |

Empty placeholder files (0 bytes, no tests yet): `backend/tests/unit/test_analyzer.py`, `unit/test_planner.py`, `unit/test_ranking.py`, `integration/test_retrieval.py`, `api/test_search.py`.

Status rules: "Passed" is used only where a commit records a passing run. Everything else is an expected result, not a claim of passing. Record new pass/fail evidence here only after running pytest.

---

## Package boundary

**Module under test:** `backend.main`, `backend.services.crawler_monitoring`  
**Test file:** `backend/tests/test_package_boundary.py`

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| PB-01 | `test_backend_import_and_routes_do_not_require_crawler` | In a fresh Python subprocess, install a meta-path finder that raises on any import of `crawler` or `indexer`, then import `backend.main.app` and `build_monitor`. `DATABASE_URL` points to an unreachable dummy host (`127.0.0.1:1`). | Subprocess exits 0 within 20 s; no crawler/indexer import happens; OpenAPI paths include `/admin/crawler/monitor` and `/admin/indexer/report` | Not run |

---

## Ranking orchestrator

**Module under test:** `backend.search.ranking.orchestrator.rank_candidates`  
**Test file:** `backend/tests/unit/test_ranking_orchestrator.py`

### Fixtures

- `session`: `AsyncMock(spec=AsyncSession)`; no live PostgreSQL connection.
- `dependencies`: monkeypatches `tokenize_query` (returns positive terms `("async",)`, negative `("async",)`) and `load_channel_statistics`.
- `CORPUS`: 100 documents, average length 100. `make_stats` builds per-document stats (length 100, document frequency 10 for the term).
- `reference_bm25(tf)`: independent BM25 expectation with k1 = 1.2, `idf = log(1 + (100 − 10 + 0.5) / (10 + 0.5))`, document length equal to the average.

BM25 arithmetic, candidate merging, validation and ordering use the real code.

### Test cases

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| RO-01 | `test_empty_candidates_skip_database_work` | Query `async`, empty candidate list | Returns `[]`; tokenizer and stats loader never awaited | Passed |
| RO-02 | `test_rejects_invalid_query_before_io` | Query `""`, `"   "`, `None`, `123` (4 cases) | `ValueError` matching "nonempty string"; no tokenizer or loader call | Passed |
| RO-03 | `test_text_mode_scores_only_text_channel` | Mode `" TeXt "` (case and whitespace), docs 2 (tf 1) and 1 (tf 3) | Order `[1, 2]`; scores equal `reference_bm25(3)` and `reference_bm25(1)`; results are `RankedHit`; tokenizer called with `config=None`; loader called once with ids `(1, 2)`, mode `"TEXT"` | Passed |
| RO-04 | `test_code_mode_scores_only_code_channel` | `SearchMode.CODE`, doc 1 tf 1, doc 2 tf 4 | Order `[2, 1]`; top score `reference_bm25(4)`; loader called once with mode `"CODE"` | Passed |
| RO-05 | `test_all_mode_merges_duplicates_and_combines_bm25` | `SearchMode.ALL`, weights text 0.5 / code 2.0, iterator of 4 hits with duplicate doc IDs and partial `search_rank`/`code_rank` | 2 results, order `[2, 1]`; score = `0.5·text_bm25 + 2.0·code_bm25`; duplicates merged keeping the max rank per field (doc 2: 0.80/0.30, doc 1: 0.40/0.90); loader awaited twice (TEXT then CODE) with ids `(1, 2)`; tokenizer awaited once | Passed |
| RO-06 | `test_equal_bm25_scores_break_ties_by_document_id` | Docs 9, 3, 5 all with tf 2 | Order `[3, 5, 9]`; a single distinct score | Passed |
| RO-07 | `test_missing_indexed_documents_are_excluded` | Candidates 1 and 2, stats exist only for doc 1 | Only `[1]` returned | Passed |
| RO-08 | `test_no_positive_terms_skips_statistics_loading` | Query `NOT async`, tokenizer returns no positive terms | Returns `[]`; loader never awaited | Passed |
| RO-09 | `test_all_mode_skips_zero_weight_channel` | Default (ALL) mode, `text_weight=0`, `code_weight=2` | Score = `2 · reference_bm25(2)`; loader called once, CODE only | Passed |
| RO-10 | `test_single_mode_ignores_channel_fusion_weights` | Text mode with `text_weight=0`, `code_weight=10` | Score = unweighted `reference_bm25(2)`; loader called once | Passed |
| RO-11 | `test_active_channel_requires_precomputed_corpus` | Text mode without `text_corpus` | `ValueError` matching "text_corpus"; no tokenizer or loader call | Passed |
| RO-12 | `test_excess_candidates_fail_before_database_work` | Generator of `MAX_CANDIDATES + 1` (201) unique hits | `ValueError` matching "unique candidates"; no tokenizer or loader call | Passed |
| RO-13 | `test_loader_error_propagates` | Loader raises `RuntimeError("statistics database unavailable")` | Same `RuntimeError` reaches the caller | Passed |
| RO-14 | `test_nonfinite_combined_score_is_rejected` | `apply_BM25` patched to return `NaN` | `ValueError` matching "invalid combined score" | Passed |

**Collected cases:** 13 ordinary + 4 parameterized (RO-02) = **17**.

---

## Full-text search (FTS)

**Component:** `backend.search.retrieval.fts.get_full_text_search`  
**Test file:** `backend/src/backend/tests/integration/test_fts.py`  
**Test type:** PostgreSQL integration tests plus validation unit tests

| ID | Test name | Scenario | Expected result |
|---|---|---|---|
| FTS-01 | `test_text_matches_and_returns_ranked_fields` | Query `python async` against English text vectors | IDs 11, 12, 15; positive `search_rank`; numeric ID/score output |
| FTS-02 | `test_code_only_match_uses_code_vector` | Query `fastapi dependency` against code vectors | Only ID 14; positive `code_rank`, zero `search_rank` |
| FTS-03 | `test_match_from_either_vector` | Query `async` with text-only and code-only documents | Matching candidates from either vector; correct individual scores |
| FTS-04 | `test_terms_split_between_vectors_do_not_match` | `python` in text and `async` only in code | ID 13 excluded for query `python async`; documents must match all terms within one vector |
| FTS-05 | `test_english_stemming_differs_from_simple` | Query `run` against English `Running` and simple `running` | Text ID 17 matches; code-only ID 16 does not |
| FTS-06 | `test_web_style_or_operator` | Query `python OR rust` | Expected six document IDs matching either branch |
| FTS-07 | `test_quoted_phrase` | Query `"python async"` | Only phrase-matching text documents returned |
| FTS-08 | `test_no_matches_returns_empty_list` | Query with a nonexistent term | Empty list, no exception |
| FTS-09 | `test_case_insensitive_search` | Compare uppercase and lowercase queries | Identical ordered document IDs |
| FTS-10 | `test_limit_and_deterministic_tie_break` | Query returning tied scores, `limit=2` | Exactly IDs 11 and 12 in ascending ID order |
| FTS-11 | `test_blank_query_does_not_touch_database` | Empty/whitespace query (3 parameters) | Empty list; session `execute` not called |
| FTS-12 | `test_non_string_query_rejected_before_database_access` | `None`, integer, list, dict (4 parameters) | `TypeError`; session `execute` not called |
| FTS-13 | `test_invalid_limit_rejected_before_database_access` | Out-of-range and wrong-type limits (7 parameters) | `ValueError`; session `execute` not called |
| FTS-14 | `test_sql_injection_like_text_is_not_executed` | SQL-shaped user input | Temporary search table remains intact with eight rows |

**Total:** 14 test functions; **25 pytest cases** after parameterization (11 PostgreSQL integration cases + 14 validation cases). Commit `563b83d` records all 25 passing.

### Test isolation

- PostgreSQL integration cases require `TEST_DATABASE_URL` with the `postgresql+asyncpg://` driver.
- Each integration case creates and populates a transaction-scoped **temporary** `search_index` table. GIN indexes are created on both vectors. The existing permanent `search_index` table and its documents remain untouched.
- The tests assume `SearchIndex` uses an unqualified table name and exposes `document_id`, `search_vector`, and `code_vector`. If the model uses an explicitly qualified schema, update the fixture instead of running against production tables.
- Missing `TEST_DATABASE_URL` causes integration cases to be **skipped**, not passed. Validation unit tests can still run.
- The actual database engine decides whether to use the GIN indexes for each query. Passing these tests verifies retrieval correctness, not execution-plan performance.

### Not covered by FTS v1

| Concern | Owner / follow-up |
|---|---|
| Maximum query length | API / Query Analyzer; not implemented in current FTS function |
| Public pagination contract | API and retrieval orchestration |
| Removed/hidden documents | Retrieval eligibility filter, once data contract is confirmed |
| BM25 ranking and score calibration | Ranking engine |
| Fuzzy matching and exact code identifier search | `retrieval/fuzzy.py` and `retrieval/code.py` |
| Query plan / latency / index usage | Separate `EXPLAIN (ANALYZE, BUFFERS)` performance benchmarks |

---

## Code retrieval

**Component:** `retrieval/code.py` (`search_code`)  
**Test file:** `backend/src/backend/tests/unit/test_code.py`

### Contract

- **Purpose:** Retrieve code-relevant *document IDs* from the already populated `search_index.code_vector`.
- **Input:** An existing SQLAlchemy `AsyncSession`, query string, `limit` (1 to 100), `offset` (0 to 10,000).
- **Output:** `list[CodeRetrievalHit]` with `document_id: int` and `score: float`.
- **Query mode:** PostgreSQL `plainto_tsquery('simple', ...)`, which uses AND between lexemes.
- **Rank:** PostgreSQL `ts_rank_cd(..., 32)`. This is a retrieval score, **not BM25**.
- **Selection:** `code_vector @@ tsquery`. This is compatible with a GIN index on `code_vector`.
- **Order:** descending retrieval score, ascending document ID for deterministic ties.
- **No ownership:** The function does not open, commit, or close the caller's database session.
- **No joins:** It must not read from `document` or perform snippet generation.

### Test matrix

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

Without `TEST_DATABASE_URL`, only C18 is skipped.

### Manual PostgreSQL checks

**Prerequisite:** The existing indexer produced the `code_vector` column using the `simple` text-search configuration. Check that `document_id` is an integer-compatible key.

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

For production query-plan assessment, run `EXPLAIN (ANALYZE, BUFFERS)` against a populated database. PostgreSQL may reasonably choose a sequential scan on a small test table even if a GIN index exists.

### Known v1 limitations

1. **AND semantics:** A query with multiple lexemes matches only indexed vectors containing all of them. OR/weighted recall belongs in a later retrieval policy.
2. **Punctuation:** PostgreSQL text-search parsing is not a byte-exact code-symbol index. `std::vector`, `foo.bar()`, `C++`, and `list[i]` need separate exact-identifier matching if punctuation matters.
3. **Rank:** `ts_rank_cd` is a preliminary rank. Do not compare it directly across heterogeneous retrievers without calibration.
4. **Performance:** Mocked unit tests do not measure latency, SQL plans, or GIN index behavior.
5. **Deletion consistency:** If the indexer deletes a document from `search_index`, this retriever should no longer return it. That belongs in indexer/retriever integration tests.
6. **Pagination stability:** Score + ID order is deterministic for a fixed index snapshot, but results can shift between requests if the index changes.

---

## Fuzzy retrieval

**Module under test:** `backend.search.retrieval.fuzzy.get_fuzzy_search`  
**Test file:** `backend/src/backend/tests/integration/test_fuzzy.py`

### Expected v1 behavior

```python
async def get_fuzzy_search(
    query: str,
    session: AsyncSession,
    limit: int = 20,
) -> list[dict[str, int | float]]:
    ...
```

Each returned row is `{"document_id": int, "fuzzy_score": float}`. Search the **document title** with PostgreSQL `pg_trgm` word similarity, rank by score descending and document ID ascending, and return no more than `limit` results. The tests set `pg_trgm.word_similarity_threshold` to `0.6`.

This is a **proposed contract**. If the design intentionally changes the name, schema, return fields or algorithm, update the tests and this section.

### Test cases

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

### Test data and isolation

The PostgreSQL fixture populates a **temporary** table whose name is derived from `Document.__table__`; this shadows the real unqualified ORM table only for the test connection. It holds 12 invented document titles, including two identical titles to verify tie-breaking. The test creates a temporary GIN trigram index, then drops everything via transaction rollback.

**Preconditions:**

1. `Document` is exported by `backend.models` and has `title` and one integer primary-key column.
2. `get_fuzzy_search` exists in `backend.search.retrieval.fuzzy` with the return contract above.
3. `TEST_DATABASE_URL` points to a dedicated PostgreSQL database **named exactly `developers_eye_test`**. The fixture refuses any other database name.
4. `pg_trgm` is installed in the test database (`CREATE EXTENSION IF NOT EXISTS pg_trgm;`).
5. The database role can create temporary tables. `pytest`, `pytest-asyncio`, `SQLAlchemy`, and `asyncpg` are installed.

### Scope and limitations

- Covers **title-based, word-similarity fuzzy candidate retrieval** only. Not covered: token-by-token autocorrection, whole-document fuzzy search, `pythno` transposition recall, BM25, query routing, snippets, HTTP pagination.
- The fixture's GIN trigram index **does not prove the planner uses it** on a 12-row table. Benchmark production-sized data with `EXPLAIN (ANALYZE, BUFFERS)`.
- Only exact-title matches are asserted to score exactly 1.0.
- If `Document` uses a schema-qualified table or UUID primary key, the fixture fails with a clear message; adapt it first.

---

## Running tests

From `developers-eye/backend/` (Windows PowerShell):

```powershell
$env:PYTHONPATH = "src"

# Suites in backend/tests (no database needed)
poetry run pytest tests -v

# Retrieval suites (integration cases need a dedicated test database)
$env:TEST_DATABASE_URL = "postgresql+asyncpg://YOUR_USERNAME:YOUR_PASSWORD@localhost:5432/developers_eye_test"
poetry run pytest src/backend/tests/integration/test_fts.py src/backend/tests/unit/test_code.py src/backend/tests/integration/test_fuzzy.py -v --tb=short
```

- Never point `TEST_DATABASE_URL` at the crawler's production database, and never commit credentials. URL-encode reserved characters in the password.
- The fuzzy suite requires the database name `developers_eye_test` and `pg_trgm` (`CREATE EXTENSION IF NOT EXISTS pg_trgm;`).
- `pytest-asyncio` is required for the async suites.

## Not covered yet

| Area | Placeholder file |
|---|---|
| Query analyzer | `backend/tests/unit/test_analyzer.py` |
| Query planner / `SearchMode` selection | `backend/tests/unit/test_planner.py` |
| BM25 / statistics functions in isolation | `backend/tests/unit/test_ranking.py` |
| Retrieval against a real PostgreSQL database | `backend/tests/integration/test_retrieval.py` |
| Search HTTP endpoint | `backend/tests/api/test_search.py` |
