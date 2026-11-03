---
id: INC-0003
title: Source max_depth was configured but never read, so the frontier grew without limit
status: resolved
date: 2026-10-20
severity: high
area: crawler
feature: url-frontier
code:
  - crawler/src/crawler/frontier/scope.py:CrawlScope
  - crawler/src/crawler/frontier/repository.py:enqueue_targets
  - crawler/src/crawler/worker/jobs/jobs.py:process_job
  - crawler/src/crawler/worker/jobs/utility.py:_create_discovered_targets
  - backend/alembic/versions/c72f318bd923_crawl_depth.py
fix_commits: [6f1ab68]
related: [ADR-0005]
---

# INC-0003: Crawl scope limits were never enforced

## Signature
No error. The symptom is a `crawl_target` count per source that keeps climbing, with no `depth` column on `crawl_target` before migration `c72f318bd923`:
```sql
SELECT source_id, count(*) FROM crawl_target GROUP BY source_id ORDER BY 2 DESC;
```

## Summary
Every source's JSON `config` carried `max_depth: 3`, and the seed plan assumed it bounded the crawl. No code read it. Every fetched page could enqueue up to `max_links` (1,000) children, each child could do the same, and there was no per-source cap, so a large documentation site could fill the frontier with millions of URLs, crowd out other sources and waste crawl budget on pages far from the seed.

> **Question for nish:** how was this found: a frontier count that looked wrong in the admin monitor, a crawl that never finished, or a code review? And roughly how big did the frontier get before the fix? A number here makes the severity concrete.

## Expected vs actual
- Expected: a source with `max_depth: 3` only crawls pages at most 3 links from a seed, and stops adding URLs after a fixed budget.
- Actual: depth was not stored on targets at all, and nothing limited the number of targets per source.

## Root cause
The configuration format was written before the frontier code, and the frontier never implemented it. There was no test asserting that a depth-4 link is not enqueued, so nothing failed.

## Fixes that did not work
None recorded.

> **Question for nish:** did you try anything first (for example only lowering `max_links`)? If so, add it here.

## Resolution
Commit `6f1ab68`:
- **Depth is stored.** Migration `c72f318bd923` adds `crawl_target.depth`. Seeds are 0; children are parent depth + 1. Existing rows were backfilled from their discovery parents; broken or cyclic chains were left outside the allowed depth instead of being treated as new seeds.
- **`CrawlScope.from_config()`** reads `max_depth` (default 3, allowed 0 to 100), `max_pages` (default 10,000, allowed 1 to 1,000,000) and `allowed_path_prefixes` (default `['/']`). `allows(url, depth)` checks `0 <= depth <= max_depth` and the URL path against the prefixes.
- **Depth is checked twice:** before fetching a page target, and before creating children. A page at the maximum depth is fetched, but its links are not enqueued. A 200 whose final URL leaves the path scope is `block`ed.
- **Per-source budget** in `enqueue_targets()`: for each source, in ascending id order, take `pg_advisory_xact_lock(hashtextextended('frontier-source:<id>', 0))`, count existing targets, and insert only up to `max_pages - count` new URLs. URLs that already exist do not use up the budget. The lock makes the count-then-insert safe across concurrent workers.
- The budget counts every target of the source, including disabled and blocked ones. Raising or lowering `max_pages` never deletes rows.

## Prevention
- Regression tests: `crawler/tests/crawler/frontier/test_scope.py` (depth limits, path traversal, invalid config), `test_enqueue_target.py` (duplicates, full budgets), `worker/tests/test_postgres_pipeline.py::test_concurrent_claims_atomic_writes_and_shared_source_budget`.
- Monitoring: none. The admin monitor shows frontier size per source, but there is no alert.
- Remaining risk:
  - the per-source advisory lock serializes link inserts for one source across all workers;
  - `max_pages` limits frontier rows, not fetched pages or stored documents; a source at its budget stops discovering new pages forever until the budget is raised.

## Rules for future changes
- Any new config key in `source.config` needs code that reads it and a test that fails if it is ignored.
- Create targets only through `enqueue_targets()` so the depth and budget rules apply.
- Keep the per-source advisory lock around the count-then-insert, and take per-source locks in ascending `source_id` order.
- Keep passing: `frontier/tests/test_scope.py`, `frontier/tests/test_enqueue_target.py`, `worker/tests/test_postgres_pipeline.py`.

## References
- `0_tech_docs/journal/update-log/07_crawl_scope.md`
