---
id: EXP-0010
title: Query plans for retrieval, frontier claiming and indexing on a copy of the real data
status: done
outcome: adopt
date: '2026-11-08'
area: backend
feature: database-schema
informs: []
---

# EXP-0010: Query plans for retrieval, frontier claiming and indexing on a copy of the real data

## Question

Do retrieval and frontier claiming use their GIN and B-tree indexes on real data, and does any hot path scan a whole table?

## Why it matters

The goal is 2M documents on one small server. A scan that costs milliseconds at 42k costs seconds at 2M, and some of these run inside write transactions.

## Setup

- Hardware / OS: Windows 11 laptop.
- Versions: PostgreSQL 18.3 in a private throwaway cluster, SQLAlchemy 2.1, asyncpg.
- Data size and source: copy of the real database, 42,114 documents, 58,141 targets, 5 hosts, 267,010 terms. `crawl_event` data excluded. VACUUM ANALYZE after load.
- Configuration: shared_buffers 512MB, work_mem 32MB, jit off.

## Method

- Baseline: statements were captured from the real code paths with a SQLAlchemy cursor hook, then run with `EXPLAIN (ANALYZE, BUFFERS)` and rolled back.
- Variable changed: added `ix_document_last_crawl_target_id`.
- Metrics: plan node and execution time.
- Runs per variant: one, on a warm cache. Times are indicative only.

## Reproduce

```
pg_dump --format=plain --no-owner --exclude-table-data=crawl_event <real> > copy.sql
createdb developers_eye_test_copy; psql -f copy.sql; vacuumdb --analyze
# hook before_cursor_execute around search_documents, claim_targets, recover_expired_leases,
# select_index_candidates, select_removal_candidates, then EXPLAIN each captured statement
```

## Results

| Path | Plan | Time |
| --- | --- | --- |
| Text retrieval, common term `python` | Bitmap on `ix_search_index_vector` | 26.7 ms |
| Code retrieval | Bitmap on `ix_search_index_code_vector` | 12.5 ms |
| Term document frequency | Bitmap on the GIN index | 21 to 30 ms |
| Fuzzy suggestion | Bitmap on `ix_search_terms_trgm` | 0.8 ms |
| Frontier claim | `ix_crawl_target_host_due`, seq scan on the 5 row `crawl_host` | 2.4 ms |
| Reaper, expired leases | `ix_crawl_target_lease` | 0.03 ms |
| Reaper, orphan attempts | `ix_crawl_attempt_unfinished` | 0.03 ms |
| Duplicate check in finalize | `ix_document_content_hash` | 0.01 ms |
| Indexer candidate selection | Seq scan on `document` | 38.7 ms |
| Indexer removal selection | Index scans | 36.3 ms |
| Source page count in enqueue | Seq scan on `crawl_target` | 8.4 ms |
| 404 document lookup, before | Seq scan on `document` | 9.0 ms |
| 404 document lookup, after | `ix_document_last_crawl_target_id` | 0.04 ms |

## Analysis

Retrieval and claiming use the intended indexes. Three scans stand out.

The 404 lookup was the real defect: it ran inside the finalize transaction, on a column with no index, and would have grown with the table. It is fixed.

Indexer selection compares two tables, so an index cannot serve it. It runs once per scan on a 10 second poll, outside any write, so it is left alone.

The source count in `enqueue_targets` scans because one source owns most targets, and it runs while holding the `frontier-source` advisory lock. Bounding the count by the source limit would help only partly, since a source near its limit still counts that many rows. It is recorded here and not changed.

A second run on PostgreSQL 16.15, the deployed version, chose the same plans for the paths rechecked: GIN bitmap for text retrieval (68 ms), `ix_crawl_target_host_due` for the claim (3.5 ms), `ix_crawl_target_lease` for the reaper, a seq scan for indexer selection (26 ms), and the new index for the 404 lookup (0.02 ms). That copy also went from e94b530df145 to head with 42,114 rows in 33 seconds, and the indexer rebuilt its first 300 rows with real code vectors.

Limits: 5 hosts means the claim's host ordering was not stressed, and the data is 2% of the target size. Query plan timings on 16 are from one run with default memory settings raised.

## Outcome

Adopt the new index. Follow-up: measure `enqueue_targets` at 2M, since it serializes finalize work for one source.
