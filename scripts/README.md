# scripts

Command-line tools for Developer's Eye: repository maintenance, search diagnostics and
relevance evaluation, end-to-end checks, and the core trade-off benchmarks. Everything
here runs from the **repository root** unless the script says otherwise.

## Which Python

There is no `.venv` at the repository root. Use the crawler's environment, which has the
backend, crawler and indexer packages installed together:

```powershell
crawler\.venv\Scripts\python.exe scripts\<script>.py --help
```

The repository-maintenance scripts use only the standard library and run with any Python 3.
Scripts that touch PostgreSQL read `DATABASE_URL` from `backend/.env` unless told otherwise.

## Repository maintenance

| Script | What it does | Writes |
| --- | --- | --- |
| `run_all_tests.py` | Runs every test suite and prints one diagnostics report (`--list`, `--only`, `--with-build`, `--save`) | `tests/reports/` with `--save` |
| `update_record_index.py` | Regenerates `0_tech_docs/record-index.md` from the ADR/INC/EXP files (`--check`, `--diff`) | the record index |
| `update_test_index.py` | Regenerates the test indexes under `tests/`; `--install-hook` installs the pre-commit hook that runs it and the record index | test indexes, `.git/hooks/pre-commit` |
| `update_docs_nav.py` | Regenerates the documentation map at the end of every README (`--check`) | READMEs |
| `update_api_map.py` | Regenerates `0_tech_docs/infra/system-architecture/api-map.md` from the code (`--check`, `--diff`, `--json`) | the API map |
| `temp_test.py` | Throwaway check of the admin crawler-report key against a local API on :8000 | nothing |

## Search diagnostics and relevance

All read only unless noted. The backend-relative ones are usually run from `backend/`
with `poetry run python ../scripts/<script>.py`.

| Script | What it does |
| --- | --- |
| `compare_rankings.py` | BM25 vs PostgreSQL `ts_rank_cd` order for one query on identical candidates (`--mode`, `--k`, `--output`) |
| `evaluate_relevance.py` | `collect` a frozen snapshot and qrel template for a query set, then `score` P@k, MRR, nDCG offline ([backend/evaluation/README.md](../backend/evaluation/README.md)) |
| `profile_search.py` | Per-stage search timing, cold vs warm DF cache, plus EXPLAIN plans (EXP-0013) |
| `search_relevance_diagnostics/` | EXP-0004 batch diagnostics with a terminal dashboard ([README](search_relevance_diagnostics/README.md)) |
| `search_relevance_metrics/evaluate_relevance.py` | EXP-0009 metric scorer for those diagnostics |
| `backfill_search_categories.py` | Previews category repairs for indexed documents; **writes only with `--apply`** |

## End-to-end

| Script | What it does |
| --- | --- |
| `e2e_search_stack.py` | Starts real FastAPI and Next.js on a database it creates and drops, and checks limits, deadlines and cancellation. Run `npm run build` in `frontend/` first |

## Core trade-off benchmarks: `tradeoffs/`

The scripts behind [CORE_TRADEOFFS.md](../CORE_TRADEOFFS.md). The step-by-step method is
[guide/tradeoffs_calculation.md](../guide/tradeoffs_calculation.md). Reports go to
`backend/reports/tradeoffs/`. They need `psutil`
(`crawler\.venv\Scripts\python.exe -m pip install psutil`) and refuse to run on any
database whose name does not start with `developers_eye_bench`, because several of them write.
Make that copy first (guide, section 0.2).

| Script | Trade-offs | What it measures |
| --- | --- | --- |
| `tradeoffs/common.py` | all | Shared helpers: CPU/RAM sampler, percentiles, relevance metrics, report writer |
| `tradeoffs/search_bench.py` | 1, 2, 3 | `ranking` BM25 vs PostgreSQL; `depth` candidate pool size; `complexity` query length |
| `tradeoffs/http_bench.py` | 4, 5 | `concurrency` users vs throughput and latency; `timeout` deadline budgets (starts its own uvicorn) |
| `tradeoffs/mock_hosts.py` | 6, 9 | Local stand-in for 64 websites on 127.0.0.1:80, so crawler tests never touch real hosts |
| `tradeoffs/crawl_bench.py` | 6, 9, 10, 15 | `workers` crawler concurrency; `mixed` crawl + search; `pool` connection pool sizes; `recrawl` changed-page yield from crawl history |
| `tradeoffs/indexer_bench.py` | 7, 8, 13 | `batch`, `concurrency`, `processes`, `vocabulary` (outbox vs direct upsert vs rebuild) |
| `tradeoffs/storage_bench.py` | 11, 12 | `scaling` 10K/50K/100K samples; `indexes` GIN vs GiST vs none |
| `tradeoffs/cloud_estimate.py` | 14 | Local vs Oracle Always Free ARM capacity and monthly cost, estimated from the other reports |

```bash
PY=crawler/.venv/Scripts/python.exe
$PY scripts/tradeoffs/search_bench.py ranking --rounds 5
$PY scripts/tradeoffs/http_bench.py concurrency --seconds 20
$PY scripts/tradeoffs/cloud_estimate.py --arm-per-core 0.45
```

Run benchmarks one at a time; two at once slow each other down.
