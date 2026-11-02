# Developer's Eye: Backend Test Cases (`backend/tests`)

**Scope:** every test currently written under `backend/tests/`.  
**Status:** Not re-run while writing this document. The ranking orchestrator suite was last recorded as passing in commit `b818adc` ("ranking all 17 test passed"); the package boundary test has no recorded run.

## Inventory

| File | Tests | Notes |
|---|---|---|
| `test_package_boundary.py` | 1 | Subprocess import check, no database needed |
| `unit/test_ranking_orchestrator.py` | 14 functions, 17 collected cases | Mocked session, tokenizer and statistics loader |
| `unit/test_analyzer.py` | 0 | Empty placeholder |
| `unit/test_planner.py` | 0 | Empty placeholder |
| `unit/test_ranking.py` | 0 | Empty placeholder |
| `integration/test_retrieval.py` | 0 | Empty placeholder |
| `api/test_search.py` | 0 | Empty placeholder |

**Total:** 15 test functions, **18 collected pytest cases**.

The other Markdown files in this folder (`test_case.md` for FTS, `test_case_code.md` for `retrieval/code.py`, `fuzzy_test_case.md` for fuzzy retrieval) describe test modules that live outside this folder and are not repeated here.

## Package boundary

**Module under test:** `backend.main`, `backend.services.crawler_monitoring`  
**Test file:** `test_package_boundary.py`

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| PB-01 | `test_backend_import_and_routes_do_not_require_crawler` | In a fresh Python subprocess, install a meta-path finder that raises on any import of `crawler` or `indexer`, then import `backend.main.app` and `build_monitor`. `DATABASE_URL` points to an unreachable dummy host (`127.0.0.1:1`). | Subprocess exits 0 within 20 s; no crawler/indexer import happens; OpenAPI paths include `/admin/crawler/monitor` and `/admin/indexer/report` | Not run |

## Ranking orchestrator

**Module under test:** `backend.search.ranking.orchestrator.rank_candidates`  
**Test file:** `unit/test_ranking_orchestrator.py`

### Fixtures

- `session`: `AsyncMock(spec=AsyncSession)`; no live PostgreSQL connection.
- `dependencies`: monkeypatches `tokenize_query` (returns positive terms `("async",)`, negative `("async",)`) and `load_channel_statistics`.
- `CORPUS`: 100 documents, average length 100. `make_stats` builds per-document stats (length 100, document frequency 10 for the term).
- `reference_bm25(tf)`: independent BM25 expectation with k1 = 1.2, `idf = log(1 + (100 − 10 + 0.5) / (10 + 0.5))`, document length equal to the average.

BM25 arithmetic, candidate merging, validation and ordering use the real code.

### Test cases

| ID | Test function | Input / scenario | Expected result | Status |
|---|---|---|---|---|
| RO-01 | `test_empty_candidates_skip_database_work` | Query `async`, empty candidate list | Returns `[]`; tokenizer and stats loader never awaited | Passed (b818adc) |
| RO-02 | `test_rejects_invalid_query_before_io` | Query `""`, `"   "`, `None`, `123` (4 cases) | `ValueError` matching "nonempty string"; no tokenizer or loader call | Passed (b818adc) |
| RO-03 | `test_text_mode_scores_only_text_channel` | Mode `" TeXt "` (case and whitespace), docs 2 (tf 1) and 1 (tf 3) | Order `[1, 2]`; scores equal `reference_bm25(3)` and `reference_bm25(1)`; results are `RankedHit`; tokenizer called with `config=None`; loader called once with ids `(1, 2)`, mode `"TEXT"` | Passed (b818adc) |
| RO-04 | `test_code_mode_scores_only_code_channel` | `SearchMode.CODE`, doc 1 tf 1, doc 2 tf 4 | Order `[2, 1]`; top score `reference_bm25(4)`; loader called once with mode `"CODE"` | Passed (b818adc) |
| RO-05 | `test_all_mode_merges_duplicates_and_combines_bm25` | `SearchMode.ALL`, weights text 0.5 / code 2.0, iterator of 4 hits with duplicate doc IDs and partial `search_rank`/`code_rank` | 2 results, order `[2, 1]`; score = `0.5·text_bm25 + 2.0·code_bm25`; duplicates merged keeping the max rank per field (doc 2: 0.80/0.30, doc 1: 0.40/0.90); loader awaited twice (TEXT then CODE) with ids `(1, 2)`; tokenizer awaited once | Passed (b818adc) |
| RO-06 | `test_equal_bm25_scores_break_ties_by_document_id` | Docs 9, 3, 5 all with tf 2 | Order `[3, 5, 9]`; a single distinct score | Passed (b818adc) |
| RO-07 | `test_missing_indexed_documents_are_excluded` | Candidates 1 and 2, stats exist only for doc 1 | Only `[1]` returned | Passed (b818adc) |
| RO-08 | `test_no_positive_terms_skips_statistics_loading` | Query `NOT async`, tokenizer returns no positive terms | Returns `[]`; loader never awaited | Passed (b818adc) |
| RO-09 | `test_all_mode_skips_zero_weight_channel` | Default (ALL) mode, `text_weight=0`, `code_weight=2` | Score = `2 · reference_bm25(2)`; loader called once, CODE only | Passed (b818adc) |
| RO-10 | `test_single_mode_ignores_channel_fusion_weights` | Text mode with `text_weight=0`, `code_weight=10` | Score = unweighted `reference_bm25(2)`; loader called once | Passed (b818adc) |
| RO-11 | `test_active_channel_requires_precomputed_corpus` | Text mode without `text_corpus` | `ValueError` matching "text_corpus"; no tokenizer or loader call | Passed (b818adc) |
| RO-12 | `test_excess_candidates_fail_before_database_work` | Generator of `MAX_CANDIDATES + 1` (201) unique hits | `ValueError` matching "unique candidates"; no tokenizer or loader call | Passed (b818adc) |
| RO-13 | `test_loader_error_propagates` | Loader raises `RuntimeError("statistics database unavailable")` | Same `RuntimeError` reaches the caller | Passed (b818adc) |
| RO-14 | `test_nonfinite_combined_score_is_rejected` | `apply_BM25` patched to return `NaN` | `ValueError` matching "invalid combined score" | Passed (b818adc) |

**Collected cases:** 13 ordinary + 4 parameterized (RO-02) = **17**.

## Running tests

From `backend/` (Windows PowerShell):

```powershell
$env:PYTHONPATH = "src"
poetry run pytest tests -v
```

Neither suite needs `TEST_DATABASE_URL`. `pytest-asyncio` must be installed for the orchestrator tests.

## Not covered yet

| Area | Placeholder file |
|---|---|
| Query analyzer | `unit/test_analyzer.py` |
| Query planner / `SearchMode` selection | `unit/test_planner.py` |
| BM25 / statistics functions in isolation | `unit/test_ranking.py` |
| Retrieval against a real PostgreSQL database | `integration/test_retrieval.py` |
| Search HTTP endpoint | `api/test_search.py` |

Add rows to this document when those files gain tests, and record pass/fail only after running pytest.
