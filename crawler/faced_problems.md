.order_by(
    CrawlTarget.priority.desc(),
    CrawlTarget.next_fetch_at.asc(),
    CrawlTarget.id.asc(),
)
.limit(limit)
.with_for_update(skip_locked=True)

## Round robin made the second worker idle (2026-10-27)

**Problem.** After round-robin BFS claiming (commit `e019701`), `claim_targets()` picked each source with `FOR UPDATE OF source SKIP LOCKED`. A row lock lasts until the transaction commits, so while worker A was claiming from a source, worker B skipped that source completely. When it was the only source with due work, B got `[]` even with hundreds of URLs waiting, and the runner sleeps `--poll-seconds` after an empty claim. The worker test `test_concurrent_claims_atomic_writes_and_shared_source_budget` failed with 2 and 0 targets instead of 2 and 2. A benchmark draining 2000 targets from one source saw about 6,500 empty claims with 4 workers and 12,000 with 8, and adding workers made it slower (136/s with 1, 92/s with 4, 70/s with 8).

**Fix.** Don't lock the source row while claiming. Read the round-robin order once without a lock, take turns in memory, lock only the targets (`FOR UPDATE OF crawl_target SKIP LOCKED`), and write `last_claimed_at` once per source at the end, in ascending source id order (same lock order for every worker, so no deadlock). With 4 workers the same drain ran at about 480/s, and with 8 at about 570/s, with no empty claims.

**Lesson.** `SKIP LOCKED` on a "parent" row like `source` skips all of its children for everyone else until commit. Lock the rows that are actually being handed out (the targets), and keep shared bookkeeping writes short and in a fixed order.

Details: `0_tech_docs/crawler/scheduler-and-leases/ADR-0001-round-robin-claims-without-source-locks.md` and `EXP-0001-claim-path-concurrency-benchmark.md`. Tests: `crawler/src/crawler/schedular/tests/test_concurrent_claims.py`.

## Search index test row without `code_vector` (2026-10-27)

**Problem.** `test_removed_page_invalidates_index_and_recovers_when_restored` inserted a `SearchIndex` row with only `search_vector`. `search_index.code_vector` is `NOT NULL` now, so the insert failed with `NotNullViolationError`.

**Fix.** The fixture now sets `code_vector=func.to_tsvector('simple', '')` as well. The indexer builds code vectors with the `simple` config, and this page has no code blocks.
