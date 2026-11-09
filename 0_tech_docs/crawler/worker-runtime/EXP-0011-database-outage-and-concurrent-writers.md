---
id: EXP-0011
title: Worker recovery from a real database restart, and crawler and indexer writers racing
status: done
outcome: adopt
date: '2026-11-08'
area: crawler
feature: worker-runtime
informs:
- INC-0035
---

# EXP-0011: Worker recovery from a real database restart, and crawler and indexer writers racing

## Question

Do the crawler and indexer loops carry on after PostgreSQL is really stopped and started, and do simultaneous crawler and indexer writes on the same documents leave the index and vocabulary correct?

## Why it matters

Mocks only prove the error types someone thought of. `crawler/src/indexer/README.md` also listed concurrent writers as untested before production.

## Setup

- Hardware / OS: Windows 11 laptop.
- Versions: PostgreSQL 18.3 in a private throwaway cluster on port 55433, SQLAlchemy 2.1, asyncpg.
- Data size and source: copy of the real database, 42,114 documents.
- Configuration: outage run used 4 crawler slots, 45 second leases, and one indexer. The crawl job was a stand-in that makes no HTTP requests and completes the target. The stress run used 4 writers and 4 indexers on one pool of 120 documents for 25 seconds, 5 documents per finalize.

## Method

- Baseline: the outage run with the old error handling restored in the harness.
- Variable changed: the fixes in INC-0035.
- Metrics: whether each loop is alive, work done after restart, leases and attempts left behind, outdated documents, deadlocks, and vocabulary compared with a full recount.
- Runs per variant: one.

## Reproduce

```
initdb -D <dir> -U postgres -A trust; pg_ctl -D <dir> -o "-p 55433" -w start
# load a plain pg_dump of the real database, then mark 2,000 documents outdated
# start run_continuous and run_worker(forever=True), then:
pg_ctl -D <dir> -m immediate -w stop
# wait 12 seconds, start again, watch for 65 seconds (lease plus reaper interval)
```

The deterministic versions run under pytest with `TEST_DATABASE_URL`: `tests/crawler/worker/test_database_faults.py`, `tests/indexer/test_concurrent_writers.py`.

## Results

Immediate stop, server back after about 15 seconds:

| | Old handling | With fixes |
| --- | --- | --- |
| Crawler loop after restart | alive | alive |
| Indexer loop after restart | dead | alive |
| Crawl jobs finished in the 10 seconds after restart | 180 | 50 |
| Expired leases left | 0 | 0 |
| Unfinished attempts on non-leased targets | 0 | 0 |
| Outdated documents at the end | 1,620 | 0 |

The crawl job counts differ because the harness has only 5 hosts and they were at different points in their holds, so they say only that work resumed.

Writers racing for 25 seconds:

| Measure | Result |
| --- | --- |
| Finalize transactions committed | 1,054 |
| Index writes: indexed / unchanged / stale | 1,471 / 988 / 1,486 |
| Errors | 0 |
| Deadlocks retried | 0 |
| Outdated documents after one settling pass | 0 |
| Vocabulary terms differing from a full recount | 0 of 267,035 |

## Analysis

The claim holds. The 1,486 stale results are the design working: the writer saw the document change and refused to store the old version.

The lock order was reviewed. `_finalize` takes the target row, then sorted advisory locks, then document rows, then the `frontier-source` lock. The indexer locks one document at a time, and the vocabulary outbox takes no shared lock. Freshness holds because `updated_at` is taken with `clock_timestamp()` after the row lock.

One deadlock remains possible and was not exercised. The noindex path locks document rows before the advisory locks, so it can cross with another finalize. `retry_deadlocked_finalization` covers it.

`vocabulary_rebuild` still needs writers stopped, as its docstring says, because it reads the index and clears the outbox in separate statements.

Limits: one run each, Windows, PostgreSQL 18.3 rather than the deployed 16, no real HTTP, and no 404 or noindex paths in the stress run. The run used the working copy of `crawler/worker/jobs/utility.py`, which had uncommitted changes moving index removal to the indexer.

## Outcome

Adopt the fixes in INC-0035. Keep the pytest versions as regressions.
