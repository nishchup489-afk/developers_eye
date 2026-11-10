# Developer's Eye: Backend Test Cases

One document for every backend test case: the tests written in `backend/tests/`, plus the retrieval suites (FTS, code, fuzzy) whose test modules live in `backend/tests/`.

## Contents

1. [Inventory](#inventory)
2. [Package boundary](#package-boundary)
3. [Ranking orchestrator](#ranking-orchestrator)
4. [Full-text search (FTS)](#full-text-search-fts)
5. [Code retrieval](#code-retrieval)
6. [Fuzzy retrieval](#fuzzy-retrieval)
7. [Query analyzer](#query-analyzer)
8. [Query planner](#query-planner)
9. [BM25 formula and ranking types](#bm25-formula-and-ranking-types)
10. [Ranking statistics retrieval (PostgreSQL)](#ranking-statistics-retrieval-postgresql)
11. [Search service pipeline](#search-service-pipeline)
12. [Search service against PostgreSQL](#search-service-against-postgresql)
13. [Pagination](#pagination)
14. [Snippets](#snippets)
15. [Fuzzy suggestions](#fuzzy-suggestions)
16. [App startup (lifespan)](#app-startup-lifespan)
17. [Search HTTP API](#search-http-api)
18. [Running tests](#running-tests)
19. [Not covered yet](#not-covered-yet)

## Inventory

| Suite | Test file | Functions | Collected cases | Status |
|---|---|---|---|---|
| Package boundary | `backend/tests/test_package_boundary.py` | 1 | 1 | Not run |
| Ranking orchestrator | `backend/tests/unit/test_ranking_orchestrator.py` | 14 | 17 | Passed (commit `b818adc`) |
| Full-text search | `backend/tests/integration/test_fts.py` | 14 | 25 | Passed (commit `563b83d`) |
| Code retrieval | `backend/tests/integration/test_code.py` | 17 | See section | 1 failing (see section) |
| Fuzzy retrieval | `backend/tests/integration/test_fuzzy.py` | 15 | 26 | Import error (see section) |
| Query analyzer | `backend/tests/unit/test_analyzer.py` | 13 | 57 | Passed (local run 2026-11-04) |
| Query planner | `backend/tests/unit/test_planner.py` | 11 | 28 | Passed (local run 2026-11-04) |
| BM25 formula and ranking types | `backend/tests/unit/test_ranking.py` | 22 | 43 | Passed (local run 2026-11-04) |
| Ranking statistics retrieval | `backend/tests/integration/test_retrieval.py` | 6 | 6 | Passed (local run 2026-11-04) |
| Search service pipeline | `backend/tests/unit/test_search_pipeline.py` | 10 | 10 | Passed (local run 2026-11-04) |
| Search service against PostgreSQL | `backend/tests/integration/test_search.py` | 5 | 14 | 3 failing (see section) |
| Pagination | `backend/tests/unit/test_pagination.py` | 3 | 8 | Passed (local run 2026-11-04) |
| Snippets | `backend/tests/unit/test_snippets.py`, `unit/test_snippet_bounds.py` | 60 | 88 | Passed (local run 2026-11-04) |
| Fuzzy suggestions | `backend/tests/unit/test_fuzzy_suggestions.py`, `backend/tests/integration/test_fuzzy_suggestions.py` | 18 | 18 | Passed (container run 2026-11-07) |
| App startup | `backend/tests/unit/test_main_lifespan_search.py` | 1 | 1 | Passed (local run 2026-11-04) |
| Search HTTP API | `backend/tests/api/test_search_route.py`, `api/test_search.py` | 3 + 8 | 8 + 16 | Passed (local run 2026-11-04) |

"Local run 2026-11-04" means Python 3.14 with PostgreSQL 16 and `TEST_DATABASE_URL` set, so the integration cases ran rather than skipped.

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
**Test file:** `backend/tests/integration/test_fts.py`  
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
**Test file:** `backend/tests/integration/test_code.py`

> **Known failure (2026-11-04):** `test_normalizes_query_and_binds_pagination` still expects `plainto_tsquery('simple', ...)`, but `code.py` now uses `websearch_to_tsquery('simple', ...)`. The test is stale, not the code.

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
**Test file:** `backend/tests/integration/test_fuzzy.py`

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

## Query analyzer

**Module under test:** `backend.search.query_analyzer.analyzer.analyze_query`, `backend.search.config.SearchConfig`  
**Test file:** `backend/tests/unit/test_analyzer.py` (moved from `integration/` on 2026-11-04: it never touches a database)

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| QA-01 | `test_valid_queries` | 19 queries: mixed whitespace, quoted phrases, `C++`, `C#`, `std::vector<T>`, `--version`, combining accents, Devanagari, emoji ZWJ, 256 chars | Whitespace collapsed outside quotes, kept inside closed quotes; NFC applied; symbols kept | Passed (local run 2026-11-04) |
| QA-02 | `test_empty_queries` | `""`, spaces, tabs, em space | `QueryValidationError` with `EMPTY` | Passed (local run 2026-11-04) |
| QA-03 | `test_disallowed_controls` | NUL, DEL, ANSI escape, VT, NEL, lone surrogates, noncharacters | `INVALID_UNICODE` or `DISALLOWED_CHARACTER`; raw input never in the message | Passed (local run 2026-11-04) |
| QA-04 | `test_rejects_unsafe_format_controls` | Bidi overrides, zero-width chars, BOM, soft hyphen (10 code points) | `DISALLOWED_CHARACTER` | Passed (local run 2026-11-04) |
| QA-05 | `test_normalized_length_rejected` | 257 chars | `TOO_LONG` | Passed (local run 2026-11-04) |
| QA-06 | `test_raw_length_checked_before_scan` | NUL plus 1024 spaces | `TOO_LONG` (length check runs before the character scan) | Passed (local run 2026-11-04) |
| QA-07 | `test_extra_whitespace_within_raw_limit` | 500 spaces + `python` + 500 spaces | `python` | Passed (local run 2026-11-04) |
| QA-08 | `test_custom_config` | `max_query_length=8` | 6 chars pass, 9 chars `TOO_LONG` | Passed (local run 2026-11-04) |
| QA-09 | `test_rejects_nonstrings` | `None`, int, dict, list, bool, bytes | `TypeError` | Passed (local run 2026-11-04) |
| QA-10 | `test_rejects_nonconfig` | `config="bad"` | `TypeError` | Passed (local run 2026-11-04) |
| QA-11 | `test_config_rejects_invalid_raw_limits` | raw limit below normalized limit, limits above 4096 / 16384 | `SearchConfigError` | Passed (local run 2026-11-04) |
| QA-12 | `test_config_read_from_env` | `SEARCH_MAX_QUERY_LENGTH=512`, `SEARCH_MAX_RAW_QUERY_LENGTH=2048` | Values read | Passed (local run 2026-11-04) |
| QA-13 | `test_invalid_env` | `SEARCH_MAX_RAW_QUERY_LENGTH=nope` | `SearchConfigError` | Passed (local run 2026-11-04) |

---

## Query planner

**Module under test:** `backend.search.query_selector.planner.select_query_plan`  
**Test file:** `backend/tests/unit/test_planner.py`

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| QP-01 | `test_mode_selects_targets` | `ALL`, `TEXT`, `CODE` | `(TEXT, CODE)`, `(TEXT,)`, `(CODE,)` | Passed (local run 2026-11-04) |
| QP-02 | `test_default_mode_is_all` | No mode | `ALL`, both targets | Passed (local run 2026-11-04) |
| QP-03 | `test_default_mode_is_used_when_mode_is_none` | `default_mode="code"`, with and without `mode="text"` | Default used only when mode is `None` | Passed (local run 2026-11-04) |
| QP-04 | `test_mode_strings_are_trimmed_and_case_insensitive` | `"TEXT"`, `" Text "`, `"\tcode\n"`, `"ALL"` | Parsed to the matching `SearchMode` | Passed (local run 2026-11-04) |
| QP-05 | `test_query_is_trimmed` | `"  python   async \n"` | `"python   async"` (inner spacing left to the analyzer) | Passed (local run 2026-11-04) |
| QP-06 | `test_empty_query_is_rejected` | `""`, spaces, tabs | `ValueError` | Passed (local run 2026-11-04) |
| QP-07 | `test_non_string_query_is_rejected` | `None`, int, bytes, list | `TypeError` | Passed (local run 2026-11-04) |
| QP-08 | `test_unknown_mode_is_rejected` | `""`, `fuzzy`, `texts`, `all code` | `ValueError` "Unsupported search mode" | Passed (local run 2026-11-04) |
| QP-09 | `test_non_string_mode_is_rejected` | int, float, list, bytes | `TypeError` | Passed (local run 2026-11-04) |
| QP-10 | `test_invalid_default_mode_is_rejected_when_used` | `default_mode="nope"` | `ValueError` | Passed (local run 2026-11-04) |
| QP-11 | `test_plan_is_immutable` | Assign to `plan.mode` | `FrozenInstanceError` | Passed (local run 2026-11-04) |

---

## BM25 formula and ranking types

**Modules under test:** `backend.search.ranking.bm25`, `backend.search.ranking.types`, input checks in `backend.search.ranking.statistics`  
**Test file:** `backend/tests/unit/test_ranking.py` (no database)

Expected scores come from `reference()`, a textbook BM25 (`idf = ln(1 + (N − df + 0.5)/(df + 0.5))`) written separately from `bm25.py`.

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| RK-01 | `test_formula_matches_reference` | 4 parameter sets incl. `df = N`, `b = 0` | Equals `reference()` | Passed (local run 2026-11-04) |
| RK-02 | `test_rarer_terms_score_higher` | df 2 vs df 90 of 100 | Rare > common > 0 | Passed (local run 2026-11-04) |
| RK-03 | `test_term_frequency_saturates` | tf 1, 2, 10, 1000 | Increasing, always below `idf · (k1 + 1)` | Passed (local run 2026-11-04) |
| RK-04 | `test_longer_documents_score_lower_when_b_positive` | dl 5 vs 50 | Shorter scores higher | Passed (local run 2026-11-04) |
| RK-05 | `test_b_zero_ignores_document_length` | `b = 0`, dl 5 vs 500 | Same score | Passed (local run 2026-11-04) |
| RK-06 | `test_apply_scores_every_candidate_and_sums_terms` | 3 candidates, terms `python`, `async` | Every candidate scored; per-term scores summed; no-match doc scores 0 | Passed (local run 2026-11-04) |
| RK-07 | `test_apply_counts_repeated_query_terms_once` | `["python", "python"]` | Same as `["python"]` | Passed (local run 2026-11-04) |
| RK-08 | `test_apply_with_no_candidates_is_empty` | No documents | `{}` | Passed (local run 2026-11-04) |
| RK-09 | `test_apply_uses_given_parameters` | `k1 = 2, b = 0` | Matches reference with those parameters | Passed (local run 2026-11-04) |
| RK-10 | `test_apply_rejects_invalid_terms` | `""`, `None` in terms | `ValueError` | Passed (local run 2026-11-04) |
| RK-11 | `test_apply_rejects_wrong_argument_types` | dict instead of stats / parameters | `TypeError` | Passed (local run 2026-11-04) |
| RK-12 | `test_bm25_parameter_defaults` | Defaults | `k1 = 1.2`, `b = 0.75` | Passed (local run 2026-11-04) |
| RK-13 | `test_bm25_parameters_reject_invalid_values` | `k1 ≤ 0`, `b` outside 0..1, inf, NaN, bool, string | `ValueError` | Passed (local run 2026-11-04) |
| RK-14 | `test_ranking_config_rejects_bad_weights` | Negative weight, both weights 0, wrong `bm25` type | `ValueError` / `TypeError`; one zero weight allowed | Passed (local run 2026-11-04) |
| RK-15 | `test_corpus_statistics_reject_invalid_values` | Negative / float count, negative avgdl, empty corpus with avgdl > 0 | `ValueError` | Passed (local run 2026-11-04) |
| RK-16 | `test_document_statistics_validation_and_freezing` | Mutate TF, id 0, tf > dl, blank term | Mapping is read-only; each invalid value raises `ValueError` | Passed (local run 2026-11-04) |
| RK-17 | `test_channel_statistics_cross_checks` | Key ≠ document_id, more candidates than N, df > N, zero avgdl with non-empty doc, wrong value type | `ValueError` / `TypeError` | Passed (local run 2026-11-04) |
| RK-18 | `test_ranking_statistics_requires_both_channels` | `code=None` | `TypeError` | Passed (local run 2026-11-04) |
| RK-19 | `test_statistics_mode_is_case_insensitive` | `text`, `TEXT`, `Code` | Upper-cased mode | Passed (local run 2026-11-04) |
| RK-20 | `test_statistics_mode_picks_vector_and_config` | `text`, `code`, `all` | `english`, `simple`; `all` raises `ValueError` | Passed (local run 2026-11-04) |
| RK-21 | `test_statistics_reject_non_lexeme_terms` | `""`, leading space, two words, tab, 257 chars | `ValueError` | Passed (local run 2026-11-04) |
| RK-22 | `test_statistics_term_and_id_limits` | Duplicate terms, a bare string, 33 terms, 201 IDs, id 0, `True` | Duplicates removed; limits and bad IDs rejected | Passed (local run 2026-11-04) |

---

## Ranking statistics retrieval (PostgreSQL)

**Module under test:** `backend.search.ranking.statistics` (DF, TF, DL read from `search_index`)  
**Test file:** `backend/tests/integration/test_retrieval.py`. Stemming, corpus averages and the BM25 flow are covered by `integration/test_ranking_statistics.py`.

### Fixture

Temporary `search_index` shadowing the real one (same approach as FTS). Words are chosen so the English stem equals the word.

| document_id | `search_vector` (english) | `code_vector` (simple) |
|---|---|---|
| 1 | `python async python` (python 2, async 1, DL 3) | empty (DL 0) |
| 2 | `python web` (DL 2) | `async def main` (DL 3) |
| 3 | `rust` (DL 1) | `async async` (async 2, DL 2) |

### Test cases

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| RS-01 | `test_document_frequencies_in_one_query` | TEXT: python, async, web, missing; CODE: async, python; empty list | `{python: 2, async: 1, web: 1, missing: 0}`, `{async: 2, python: 0}`, `{}` | Passed (local run 2026-11-04) |
| RS-02 | `test_candidate_term_frequencies_and_lengths` | IDs 1, 2, 3, 99 in TEXT | Doc 1: DL 3, python 2, async 1; doc 2: DL 2, python 1; doc 3: DL 1, no terms; 99 left out | Passed (local run 2026-11-04) |
| RS-03 | `test_code_channel_reads_code_vector` | IDs 1, 3 in CODE | Doc 1 DL 0; doc 3 DL 2, async 2 | Passed (local run 2026-11-04) |
| RS-04 | `test_single_document_helpers` | `_get_term_frequency`, `_get_document_length` | 2, 0, `None` for an unindexed ID; code DL 3 | Passed (local run 2026-11-04) |
| RS-05 | `test_load_channel_statistics_without_candidates_skips_queries` | No candidate IDs | Same corpus object, empty DF and documents | Passed (local run 2026-11-04) |
| RS-06 | `test_load_channel_statistics_validates_inputs` | `corpus=None`, mode `ALL`, term `python async` | `TypeError`, `ValueError`, `ValueError` | Passed (local run 2026-11-04) |

---

## Search service pipeline

**Module under test:** `backend.search.service.search_documents`, `categorize`  
**Test file:** `backend/tests/unit/test_search_pipeline.py` (retrieval, ranking and the session are mocked)

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| SP-01 | `test_all_mode_merges_candidates_preserves_scores_and_generates_snippets` | Same doc from text (0.6) and code (0.9) | One hit with both ranks passed to BM25; BM25 score kept; snippet contains the term; query normalized | Passed (local run 2026-11-04) |
| SP-02 | `test_text_mode_does_not_query_code` | `mode=TEXT` | Code retrieval never awaited | Passed (local run 2026-11-04) |
| SP-03 | `test_code_mode_does_not_query_text_and_uses_code_block` | `mode=CODE` | Text retrieval never awaited; snippet keeps the code block | Passed (local run 2026-11-04) |
| SP-04 | `test_filter_before_pagination_and_preserve_bm25_order` | Category filter with pages | Filter runs before paging; BM25 order kept; 2 DB round trips | Passed (local run 2026-11-04) |
| SP-05 | `test_unavailable_and_invalid_urls_removed_before_paging` | Unavailable doc and invalid URL | Removed before paging | Passed (local run 2026-11-04) |
| SP-06 | `test_no_hits_skips_bm25_and_metadata` | No retrieval hits | `[]`; ranking and metadata never queried | Passed (local run 2026-11-04) |
| SP-07 | `test_invalid_pagination_rejected_without_db_access` | page 0 / bool, limit 0 / bool, too large | `ValueError`; no DB call | Passed (local run 2026-11-04) |
| SP-08 | `test_uninitialized_stats_rejected_with_nonempty_retrieval` | Corpus snapshots cleared | `RuntimeError` | Passed (local run 2026-11-04) |
| SP-09 | `test_source_category_host_must_match_domain_boundary` | `notgithub.com`, `docs.github.com`, `stackoverflow.com` | `articles`, `github`, `stackoverflow` | Passed (local run 2026-11-04) |
| SP-10 | `test_no_eligible_metadata_skips_body_and_snippet` | Metadata filters out every hit | Body and snippet never loaded | Passed (local run 2026-11-04) |

---

## Search service against PostgreSQL

**Module under test:** `backend.search.service.search_documents`, `categorize`  
**Test file:** `backend/tests/integration/test_search.py` (temporary `document` and `search_index` tables)

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| SS-01 | `test_returns_frontend_shaped_results` | Query `async` | Results shaped for the frontend (url, source, snippet, tags) | Failing: `RuntimeError` BM25 corpus statistics not initialized |
| SS-02 | `test_unavailable_documents_are_hidden` | Query matching only an unavailable doc | `[]` | Failing: same cause |
| SS-03 | `test_category_filter_and_limit` | `category="github"` and a limit | Only the GitHub issue | Failing: same cause |
| SS-04 | `test_no_match_returns_empty` | `kubernetes` | `[]` | Passed (local run 2026-11-04) |
| SS-05 | `test_categorize` | 5 URL / type pairs | Expected category | Passed (local run 2026-11-04) |

> **Known failure (2026-11-04):** the fixture predates BM25 ranking. It never loads corpus snapshots, so any query with hits raises `RuntimeError`. The fixture needs to load corpus statistics (as `main.lifespan` does) before searching.

---

## Pagination

**Module under test:** `backend.search.pagination.paginate_hits`  
**Test file:** `backend/tests/unit/test_pagination.py`

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| PG-01 | `test_pages_preserve_ranking` | 12 hits, page 2, limit 5 | IDs 6 to 10; 3 pages; has next and previous; input not mutated | Passed (local run 2026-11-04) |
| PG-02 | `test_empty_page_and_empty_pool` | Empty pool; page past the end | 0 pages; empty page with no next | Passed (local run 2026-11-04) |
| PG-03 | `test_invalid_args` | page 0 / bool / 500, limit 0 / bool / 51 | `ValueError` | Passed (local run 2026-11-04) |

---

## Snippets

**Module under test:** `backend.search.snippets` (pure Python)  
**Test files:** `backend/tests/unit/test_snippets.py`, `backend/tests/unit/test_snippet_bounds.py`

| Group | Tests | What is checked | Status |
|---|---|---|---|
| `TestNormalizeSnippetText` | 8 | Prose whitespace collapsed, CRLF/CR normalized, NFC, code indentation kept, blank input empty, bad types rejected | Passed (local run 2026-11-04) |
| `TestHighlightSpans` | 15 | End-exclusive offsets, case-insensitive, whole words only, longest overlapping term wins, punctuation literal, duplicates once, Unicode code points, term count and length limits | Passed (local run 2026-11-04) |
| `TestPassageScore` | 6 | Zero for no match, distinct-term coverage rewarded, repeat bonus capped at 3, invalid passage rejected | Passed (local run 2026-11-04) |
| `TestCandidatePassages` | 10 | Short doc returned whole, matches near the end found, sorted by relevance, slices match normalized text, prefix fallback, count capped, bad limits rejected | Passed (local run 2026-11-04) |
| `TestGenerateSnippet` | 18 | Window around the match, description fallback, body match beats description, code mode indentation, HTML kept as plain text, one-shot generators, immutability, highlights inside the final text | Passed (local run 2026-11-04) |
| `test_snippet_never_exceeds_character_budget` | 10 | Budgets 1 to 80, prose and code | Text never longer than the budget; highlights in range | Passed (local run 2026-11-04) |
| `test_candidate_windows_respect_budget` | 2 | Candidate passages, prose and code | Every passage within `max_chars` | Passed (local run 2026-11-04) |
| `test_fallback_description_is_bounded` | 1 | Long description fallback, budget 17 | Within budget, no highlights | Passed (local run 2026-11-04) |

---

## Fuzzy suggestions

**Module under test:** `backend.search.retrieval.fuzzy.correction.suggest_query_correction`  
**Test file:** `backend/tests/unit/test_fuzzy_suggestions.py` (vocabulary lookups mocked)

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| FS-01 | `test_corrects_spelling_using_vocabulary` | `pythonn`, candidate `python` (similarity 0.9) | Suggests `python`, edit distance 1 | Passed (local run 2026-11-04) |
| FS-02 | `test_does_not_modify_exact_terms` | `python` exists in vocabulary | Unchanged; fuzzy lookup never awaited | Passed (local run 2026-11-04) |
| FS-03 | `test_does_not_correct_technical_identifier` | `AsyncSession fastapi.utils` | Unchanged; fuzzy lookup never awaited | Passed (local run 2026-11-04) |
| FS-04 | `test_stem_candidate_is_shown_as_a_real_word` | `fastapi configuraton`, candidate stem `configur` | Suggests `fastapi configuration` (edit distance 1), not the stem | Passed (container run 2026-11-07) |
| FS-05 | `test_y_stem_is_shown_as_a_real_word` | `libary`, candidate stem `librari` | Suggests `library` | Passed (container run 2026-11-07) |
| FS-06 | `test_unverified_forms_never_surface_a_bare_stem` | `configuraton`, no form reduces to `configur` | Unchanged | Passed (container run 2026-11-07) |
| FS-07 | `test_bare_stem_ending_in_i_is_skipped` | `querie`, candidate `queri` | Unchanged | Passed (container run 2026-11-07) |
| FS-08 | `test_word_whose_stem_is_indexed_is_not_a_typo` | `configuration`, vocabulary has `configur` | Unchanged; fuzzy lookup never awaited | Passed (container run 2026-11-07) |
| FS-09 | `test_surface_forms_start_with_the_stem_and_rebuild_y_words` | `surface_forms("librari")` | Stem first, includes `library`/`libraries`, no duplicates | Passed (container run 2026-11-07) |

**Integration file:** `backend/tests/integration/test_fuzzy_suggestions.py` (real PostgreSQL `english_stem` and `pg_trgm`; temp `search_terms` built from `to_tsvector('english', ...)`; needs `TEST_DATABASE_URL`)

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| FSI-01 | `test_vocabulary_holds_stems` | Vocabulary from the corpus sentence | Contains `configur`, `librari`, `python`, `cach`; not `configuration` | Passed (container run 2026-11-07) |
| FSI-02 | `test_english_stems_matches_the_index` | `Configuration`, `libraries`, `python`, `the` | `configur`, `librari`, `python`, `None` | Passed (container run 2026-11-07) |
| FSI-03 | `test_typo_suggests_a_real_word` | `configuraton`, `libary`, `pyhton`, `databse`, `fastapi configuraton` | Real words (`configuration`, `library`, `python`, `database`); never a stem | Passed (container run 2026-11-07) |
| FSI-04 | `test_correct_words_are_left_alone` | `configuration`, `libraries`, `caching`, `python` | Unchanged | Passed (container run 2026-11-07) |

---

## App startup (lifespan)

**Module under test:** `backend.main.lifespan`  
**Test file:** `backend/tests/unit/test_main_lifespan_search.py`

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| LS-01 | `test_startup_loads_both_corpus_snapshots` | Lifespan with stubbed session and statistics | TEXT then CODE corpus loaded once at startup; snapshots cleared and engine disposed on shutdown | Passed (local run 2026-11-04) |

---

## Search HTTP API

**Module under test:** `backend.api.search` (`GET /search`, `GET /search/suggest`)  
**Test files:** `backend/tests/api/test_search_route.py` (basic contract), `backend/tests/api/test_search.py` (parameters, error mapping, suggestions). The session factory and services are stubbed; no database.

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| API-01 | `test_search_route.py::test_returns_results` | `q="  fastapi   async "`, `source=docs` | 200, `Cache-Control: no-store`, normalized query, frontend shape | Passed (local run 2026-11-04) |
| API-02 | `test_search_route.py::test_rejects_invalid_input` | No q, blank q, 301 chars, NUL, bad source, limit 0 | 422; service not called | Passed (local run 2026-11-04) |
| API-03 | `test_search_route.py::test_database_error_is_503` | Service raises `OperationalError` | 503; error detail not leaked | Passed (local run 2026-11-04) |
| API-04 | `test_default_request_keeps_old_call_signature` | Only `q` | `page` and `mode` not passed to the service | Passed (local run 2026-11-04) |
| API-05 | `test_page_and_mode_are_forwarded` | page 3, mode code, limit 50 | Forwarded as `page=3`, `mode=SearchMode.CODE`, `limit=50` | Passed (local run 2026-11-04) |
| API-06 | `test_out_of_range_parameters_are_422` | limit 51, page 0 / −1, mode fuzzy, limit "ten", 1025-char q | 422; service not called | Passed (local run 2026-11-04) |
| API-07 | `test_service_validation_errors_are_422` | Service raises `ValueError` / `QueryValidationError` | 422 | Passed (local run 2026-11-04) |
| API-08 | `test_uninitialized_engine_is_503` | Service raises `RuntimeError` | 503 "Search engine is not initialized"; no detail leaked | Passed (local run 2026-11-04) |
| API-09 | `test_suggest_returns_correction_for_normalized_query` | `/search/suggest?q=  pyhton   async ` | Service gets `pyhton async`; correction returned | Passed (local run 2026-11-04) |
| API-10 | `test_suggest_rejects_invalid_query` | No q, blank, NUL | 422; service not called | Passed (local run 2026-11-04) |
| API-11 | `test_suggest_database_error_is_503` | Service raises `OperationalError` | 503; detail not leaked | Passed (local run 2026-11-04) |

---

## Running tests

From `developers-eye/backend/` (Windows PowerShell):

```powershell
$env:PYTHONPATH = "src"

# Suites in backend/tests (no database needed)
poetry run pytest tests -v

# Retrieval suites (integration cases need a dedicated test database).
# TEST_DATABASE_URL is read from the repo-root .env.local; the line below is only
# needed to override it for one terminal.
$env:TEST_DATABASE_URL = "postgresql+asyncpg://YOUR_USERNAME:YOUR_PASSWORD@localhost:5432/developers_eye_test"
poetry run pytest tests/integration -v --tb=short
```

- Never point `TEST_DATABASE_URL` at the crawler's production database, and never commit credentials. URL-encode reserved characters in the password.
- The fuzzy suite requires the database name `developers_eye_test` and `pg_trgm` (`CREATE EXTENSION IF NOT EXISTS pg_trgm;`).
- `pytest-asyncio` is required for the async suites.

## Not covered yet

- `integration/test_fuzzy.py` imports `get_fuzzy_search` from `backend.search.retrieval.fuzzy`, which no longer exists (fuzzy now lives in `candidates.py` and `correction.py`), so the whole file fails to import.
- `test_package_boundary.py` fails: it imports `backend.services.crawler_monitoring`, but the package is now `backend.admin_services`.

## Search pipeline cases (merged from the old backend/tests)




## Public search limits (ADR-0046)

`tests/api/test_search_limits.py` stubs the database. `tests/integration/test_search_deadlines.py` needs `TEST_DATABASE_URL` (database name containing `test`) and writes no rows. `scripts/e2e_search_stack.py` is the full-stack run: real Next.js and FastAPI on a new database it creates and drops; build the frontend first.

| Test | What it checks |
|---|---|
| `test_bucket_allows_burst_then_reports_wait_and_refills`, `test_buckets_are_per_client_and_bounded`, `test_zero_rate_disables_the_limit` | Token bucket behaviour and bounded memory. |
| `test_search_rate_limit_is_429_with_retry_after`, `test_suggest_rate_limit_is_separate_from_search`, `test_forwarded_clients_get_their_own_buckets` | 429 with `Retry-After`, separate search and suggestion budgets, one bucket per forwarded client. |
| `test_full_concurrency_cap_is_503_with_retry_after`, `test_concurrent_burst_admits_only_the_cap`, `test_suggestions_share_the_concurrency_cap` | 503 at the cap, and a burst in one event-loop turn cannot overshoot it. |
| `test_failed_requests_release_their_slot`, `test_validation_failure_does_not_take_a_slot` | Slots are released on failures and never taken for invalid input. |
| `test_total_deadline_is_504_and_cancels_the_search`, `test_statement_timeout_is_504`, `test_connection_pool_timeout_is_504`, `test_suggest_deadline_and_statement_timeout_are_504` | Every kind of timeout is 504 and leaks no database text. |
| `test_disconnect_cancels_search_and_frees_its_slot`, `test_disconnect_cancels_suggestion`, `test_deadline_waits_for_cancelled_work_to_unwind` | A disconnect cancels the work; a deadline waits for it to unwind. |
| `test_frontend_query_limits_match_the_backend` | `frontend/lib/search.ts` and `SearchConfig` have the same limits. |
| `test_real_statement_timeout_is_504` | A real PostgreSQL `statement_timeout` is recognised, on both routes. |
| `test_total_deadline_stops_the_postgres_query`, `test_client_disconnect_stops_the_postgres_query` | The abandoned query leaves `pg_stat_activity` well before it would have finished. |

## Admin system reporting (PostgreSQL)

`tests/integration/test_system_reporting.py` builds the full schema in a throwaway schema inside one rolled-back transaction. Requires `TEST_DATABASE_URL` (database name containing `test`, with `pg_trgm`).

| Test | What it checks |
|---|---|
| `test_system_report_budget_progress_and_yield` | Database size equals budget `used_bytes`; bytes per document, target bytes per document and documents that fit; table list includes `indexer_worker`; progress counts DEDUP `new` events for per-day rate and ETA; per-source yield, duplicates by content hash; events past retention. |
| `test_budget_status_thresholds` | `ok` under 80%, `warning` at 80% or when the projection to the goal overflows, `critical` at 95%; no documents gives null projections. |
| `test_host_report_rates_and_flags` | Host extracted from URLs with query strings; attempts, 5-minute rate, share, 429 counts; `throttled` and `hot` flags; polite and worst-case rates from the configured gap and online workers. |
| `test_problems_detect_stale_workers_throttling_and_retention` | Stale crawler and indexer heartbeats, no crawler online with due work, index lag, critical budget, projection over budget, host throttling and old events; critical problems sort first. |
| `test_problems_quiet_on_healthy_system` | A healthy system (worker online, everything indexed, within budget) reports no problems. |
| `test_purge_events_deletes_only_old_rows` | Dry run counts old events; purge in batches of 1 deletes only rows older than the retention window. |
| `test_indexer_report_lists_heartbeats` | The indexer report lists heartbeat rows with `online` / `stopped` status and counts online workers. |
