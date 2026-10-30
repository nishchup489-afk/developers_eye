# Developer's Eye: Full-Text Search Test Cases

**Component:** `backend.search.retrieval.fts.get_full_text_search`  
**Test file:** `test_fts.py`  
**Test type:** PostgreSQL integration tests plus validation unit tests  
**Status:** **Not executed**. Results below are expected behavior, not claims of passing tests.

## Test coverage

| ID | Test name | Scenario | Expected result | Status |
|---|---|---|---|---|
| FTS-01 | `test_text_matches_and_returns_ranked_fields` | Query `python async` against English text vectors | IDs 11, 12, 15; positive `search_rank`; numeric ID/score output | Not run |
| FTS-02 | `test_code_only_match_uses_code_vector` | Query `fastapi dependency` against code vectors | Only ID 14; positive `code_rank`, zero `search_rank` | Not run |
| FTS-03 | `test_match_from_either_vector` | Query `async` with text-only and code-only documents | Matching candidates from either vector; correct individual scores | Not run |
| FTS-04 | `test_terms_split_between_vectors_do_not_match` | `python` in text and `async` only in code | ID 13 excluded for query `python async`; documents must match all terms within one vector | Not run |
| FTS-05 | `test_english_stemming_differs_from_simple` | Query `run` against English `Running` and simple `running` | Text ID 17 matches; code-only ID 16 does not | Not run |
| FTS-06 | `test_web_style_or_operator` | Query `python OR rust` | Expected six document IDs matching either branch | Not run |
| FTS-07 | `test_quoted_phrase` | Query `"python async"` | Only phrase-matching text documents returned | Not run |
| FTS-08 | `test_no_matches_returns_empty_list` | Query with a nonexistent term | Empty list, no exception | Not run |
| FTS-09 | `test_case_insensitive_search` | Compare uppercase and lowercase queries | Identical ordered document IDs | Not run |
| FTS-10 | `test_limit_and_deterministic_tie_break` | Query returning tied scores, `limit=2` | Exactly IDs 11 and 12 in ascending ID order | Not run |
| FTS-11 | `test_blank_query_does_not_touch_database` | Empty/whitespace query (3 parameters) | Empty list; session `execute` not called | Not run |
| FTS-12 | `test_non_string_query_rejected_before_database_access` | `None`, integer, list, dict (4 parameters) | `TypeError`; session `execute` not called | Not run |
| FTS-13 | `test_invalid_limit_rejected_before_database_access` | Out-of-range and wrong-type limits (7 parameters) | `ValueError`; session `execute` not called | Not run |
| FTS-14 | `test_sql_injection_like_text_is_not_executed` | SQL-shaped user input | Temporary search table remains intact with eight rows | Not run |

**Total:** 14 test functions; **25 pytest cases** after parameterization (11 PostgreSQL integration cases + 14 validation cases).

## Test isolation

- PostgreSQL integration cases require `TEST_DATABASE_URL` with the `postgresql+asyncpg://` driver.
- Each integration case creates and populates a transaction-scoped **temporary** `search_index` table. GIN indexes are created on both vectors. The existing permanent `search_index` table and its documents remain untouched.
- The tests assume `SearchIndex` uses an unqualified table name and exposes `document_id`, `search_vector`, and `code_vector`. If the model uses an explicitly qualified schema, update the fixture instead of running against production tables.
- Missing `TEST_DATABASE_URL` causes integration cases to be **skipped**, not passed. Validation unit tests can still run.
- The actual database engine decides whether to use the GIN indexes for each query. Passing these tests verifies retrieval correctness, not execution-plan performance.

## Running tests

From the `backend/` directory (with the appropriate Python environment and import path):

```powershell
$env:PYTHONPATH = "src"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/developers_eye_test"
poetry run pytest src/backend/tests/integration/test_fts.py -v
```

Replace the URL example with **your separate test database**. Never use the crawler's production database for test fixtures.

## Not covered by FTS v1

| Concern | Owner / follow-up |
|---|---|
| Maximum query length | API / Query Analyzer; not implemented in current FTS function |
| Public pagination contract | API and retrieval orchestration |
| Removed/hidden documents | Retrieval eligibility filter, once data contract is confirmed |
| BM25 ranking and score calibration | Ranking engine |
| Fuzzy matching and exact code identifier search | `retrieval/fuzzy.py` and `retrieval/code.py` |
| Query plan / latency / index usage | Separate `EXPLAIN (ANALYZE, BUFFERS)` performance benchmarks |

**Record actual pass/fail evidence here only after running pytest.**
