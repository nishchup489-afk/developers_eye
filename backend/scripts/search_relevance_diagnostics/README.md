# Developer's Eye: EXP-0004 batch diagnostics

Adds a 100-query, read-only batch diagnostic to the existing Developer's Eye backend.
No existing source files need to be edited.

## Files

- `backend/scripts/diagnose_relevance.py`: Rich terminal dashboard and read-only query runner.
- `backend/evaluation/diagnostic_queries.json`: Editable 100-query suite (10 thematic groups × 10 queries).

## Install and run

Place the two files in the matching paths within your `developers-eye` clone. Open a terminal in `backend/`.

```powershell
poetry add --group dev rich
poetry run python scripts/search_relavance_diagnostics/diagnose_relevance.py --limit 5 --details
poetry run python scripts/search_relavance_diagnostics/diagnose_relevance.py --k 10
```

To inspect specific cases without rerunning all 100:

```powershell
poetry run python scripts/diagnose_relevance.py --id Q051 --details
poetry run python scripts/diagnose_relevance.py --id Q024 --id Q061 --details
```

Useful IDs: Q011 `python async api`, Q024 `FastAPI Depends`, Q051 `javascript fetch examples`, Q061 `HTTP 404`.

Optional arguments:

- `--limit 10`: smoke test with the first 10 queries.
- `--k 20`: compare the top 20 rather than top 10.
- `--slow-ms 10000`: slow-query threshold.
- `--output-dir reports/exp-0004`: report directory.
- `--suite evaluation/diagnostic_queries.json`: different input suite.
- `--no-color`: disable ANSI colors.

## Outputs

Each run creates `backend/reports/exp-0004/<UTC-timestamp>-<count>q/` containing:

- `diagnostics.json`: all ranks, scores, timings, document titles/URLs, and flags for every query.
- `diagnostics.md`: human-readable report, per-query overview, and expanded flagged-query top-K lists.
- `terminal.html`: Rich terminal view exported as HTML.

The terminal shows a progress bar, full per-query table, and category summary.
Use `--details` for two-column BM25 vs PostgreSQL tables.

## What this does and does not measure

It measures ranked-list overlap, candidate counts, elapsed time, URL-locale heuristics, and whether specific expected-title substrings appear near the top. This is a **diagnostic**, not a judged relevance evaluation: title hints are not qrels, and agreement cannot substitute for P@10, MRR@10, nDCG@10, or Recall@100. The runner does not call the public UI route, so UI snippets and metadata filtering are outside its scope.

It uses the production retrieval and BM25 functions, with the same candidate budget (100 per channel). PostgreSQL scores are recomputed on the **same candidate IDs**, with the CODE channel `ts_rank_cd` normalization set to `32` to match the code retriever. For ALL, the PostgreSQL comparator is an explicitly unweighted sum; it is *not* a separate retrieval policy or an exact replica of the public service pipeline.

Corpus statistics are scanned once per active channel at the start of a run. Each query runs in its own PostgreSQL `REPEATABLE READ, READ ONLY` transaction. The crawler may mutate the corpus between queries, so run with the crawler paused for reliable before/after comparisons. This script makes no database writes.

`TARGET_NOT_IN_CANDIDATES` says the expected title was not present in the returned 100/200 candidates, **not** that the underlying document is absent from the whole index. `LOW_AGREEMENT` says two scorers disagree, **not** which one is better. `MULTILINGUAL_TOP` uses path-based language guesses, not document-language detection.
