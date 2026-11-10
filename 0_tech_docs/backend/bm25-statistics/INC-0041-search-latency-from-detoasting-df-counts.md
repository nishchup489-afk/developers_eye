---
id: INC-0041
title: Searches took 5-11 s because BM25 document-frequency counts scanned every vector
status: resolved
date: 2026-11-10
severity: high
area: backend
feature: bm25-statistics
code: [backend/src/backend/search/ranking/statistics.py:_get_document_frequencies]
fix_commits: [3453f76]
related: [EXP-0016, ADR-0027, ADR-0057]
---

# INC-0041: Searches took 5-11 s because BM25 document-frequency counts scanned every vector

## Signature
```
100k-document evaluation run: 9 of the evaluated queries over 5 s
"HTTP 500 internal server error" 10.7 s, "python context manager" 7.7 s
EXPLAIN (ANALYZE, BUFFERS) on PostgreSQL 18:  Seq Scan on search_index ... 1130 ms, ~340k shared buffers
```

## Summary
At about 100k documents, ordinary multi-word searches took 5 to 11 seconds. Each search counts, for
every query term, how many documents contain it (BM25 document frequency). For common terms such as
`python`, `error` or `http` the planner switched from the GIN index to a sequential scan of
`search_index`, which detoasts every stored `tsvector` (about 1 s and 340k buffers per term). Several
terms per query, times two channels in `all` mode, gave multi-second searches.

## Expected vs actual
- Expected: document-frequency lookups are index-only work that stays in tens of milliseconds as the corpus grows.
- Actual: they grew linearly with the corpus and dominated search time (the "ranking" stage).

## Timeline
1. The user's 100k evaluation reported nine queries over 5 s.
2. Profiling the stages showed ranking, not retrieval, held the time; inside ranking the DF query did.
3. The user's PG18 plan showed the seq scan. On a 126k scaled copy the same SQL with seq scans took
   0.97–1.83 s per query versus 18–67 ms on the GIN index (EXP-0016).

## Root cause
`count(*) WHERE vector @@ 'term'::tsquery` is estimated from `tsvector` statistics. For a lexeme in a
large share of rows the planner prices a sequential scan below a bitmap scan, but it does not price the
cost of detoasting large vectors, which is most of the real work. The GIN bitmap only reads posting
lists and never detoasts.

## Fixes that did not work
| Attempt | Why it failed |
| --- | --- |
| Rely on the DF cache alone | A cold or new term still pays the full scan, and the 100k run was mostly cold terms. |

## Resolution
`_get_document_frequencies` runs inside `_gin_only_plans`, which sets `enable_seqscan = off` with
`set_config(..., true)` (transaction-local) for that one statement and then restores the previous value,
so other statements in the same transaction keep normal planning. Counts are identical (checked per term
in EXP-0016). Cold searches on the 126k copy went from 1.07–1.97 s to 61–275 ms.

## Prevention
- Regression test: `tests/integration/test_ranking_statistics.py::test_df_counts_use_the_gin_index_not_a_detoasting_seq_scan`.
- Monitoring: slow and timed-out searches are now recorded with per-stage timings and shown on the admin
  Search quality page (ADR-0057), so a regression shows which stage it is in.
- Remaining risk: the setting forbids seq scans only for that statement; if the GIN index is missing the
  query falls back to a seq scan anyway (PostgreSQL treats the setting as a cost penalty).

## Rules for future changes
- Keep DF counts on the GIN index; do not remove `_gin_only_plans` without re-running EXP-0016 at ≥100k documents.
- Do not use session-level `SET`; the setting must stay transaction-local and be restored after the statement.
