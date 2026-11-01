---
id: INC-0002
title: Multi-worker stress test deadlocked crawl finalization and left attempts unfinished
status: resolved
date: 2026-10-20
severity: high
area: crawler
feature: worker-runtime
code:
  - crawler/src/crawler/frontier/repository.py:enqueue_targets
  - crawler/src/crawler/worker/jobs/jobs.py:retry_deadlocked_finalization
  - crawler/src/crawler/worker/jobs/jobs.py:process_job
  - crawler/src/crawler/worker/jobs/utility.py:_finalize
  - crawler/src/crawler/worker/recovery.py:recover_failed_claim
  - crawler/src/crawler/schedular/repository.py:recover_expired_leases
fix_commits: [0653690, 5e6b49e, f19c53b]
related: [ADR-0004, ADR-0006]
---

# INC-0002: Deadlocks in crawl finalization under several workers

## Signature
```
OperationalError: (psycopg.errors.DeadlockDetected) deadlock detected
CONTEXT: while inserting index tuple in relation "crawl_target"
```
In the admin monitor: attempts with no `finished_at`, and jobs that fetched and parsed fine but failed at `STORE`.

## Summary
The crawler had only been run with one worker. During a multi-worker stress test on 2026-10-20, workers fetched and processed pages correctly but some of them failed while saving. PostgreSQL detected deadlocks in the `_finalize()` transaction (document upsert, child-link inserts into `crawl_target`, target transition, attempt update). The job failed on the first deadlock, the fetched content was thrown away, and its `crawl_attempt` row stayed unfinished. The original write-up reports "hundreds of persistence failures and unfinished attempts". Lease expiry eventually requeued the targets, but with no failure count and no backoff.

> **Question for nish:** how many workers and what concurrency did the stress test use, and against which sources? If you still have the logs, add the count of failed jobs out of the total.

## Expected vs actual
- Expected: N workers finalize their jobs independently; at worst one waits briefly for another's row lock.
- Actual: concurrent finalizations formed lock cycles; PostgreSQL aborted one transaction per cycle with SQLSTATE `40P01`, and nothing retried it.

## Timeline
1. Single-worker baseline passed (`CLAIM claimed=1`, `DONE outcome=success`).
2. Multi-worker stress test: deadlocks while inserting into `crawl_target`, plus many unfinished attempts.
3. `0653690` (20:44): sort and deduplicate child links before insert; add `retry_deadlocked_finalization()`.
4. `5e6b49e` (20:50): the retry helper had been added but `process_job()` still called `_finalize()` directly. It is now wrapped.
5. `f19c53b` (20:55): failed jobs close their own attempt and back off; expired leases count as failures (see ADR-0006).

## Root cause
Several workers discovered overlapping links and inserted them with `INSERT ... ON CONFLICT DO NOTHING` in the order each one found them. `ON CONFLICT` still takes locks on the unique index entries for `(source_id, normalized_url)`. Two transactions that insert the same keys in different orders can each hold one key and wait for the other's, which is a deadlock. The same transaction also updated documents, took advisory locks and wrote attempts, which adds more possible cycles.

The write-up says the two-worker example is an illustration, not a reconstruction from the logs. **The exact lock cycle was not captured.**

> **Question for nish:** did you ever see the full deadlock detail (the "Process X waits for ShareLock on transaction Y" lines in the Postgres server log)? If so, paste the relevant lines; it would confirm whether the cycle was only in `crawl_target`.

## Fixes that did not work
| Attempt | Why it failed |
| --- | --- |
| Rely on `ON CONFLICT DO NOTHING` to make concurrent inserts safe | It prevents duplicate rows, not lock-order cycles on the unique index. |
| Add `retry_deadlocked_finalization()` (`0653690`) | It was never called; `process_job()` still called `_finalize()` directly until `5e6b49e`. |
| Rely on lease expiry to clean up after a failed finalize | The target came back, but the attempt stayed unfinished and the target was retried immediately with no backoff (fixed in `f19c53b`). |

## Resolution
1. **Deterministic insert order** (`frontier/repository.py:enqueue_targets`): deduplicate by `(source_id, normalized_url)`, sort by that key, then insert in batches. Overlapping keys are now locked in the same order by every worker.
2. **Retry only the database part** (`jobs.py:retry_deadlocked_finalization`): retry `_finalize()` up to 4 attempts when `exc.orig.sqlstate == "40P01"`, sleeping `min(0.2 × 2^(n−1), 2.0) + uniform(0, 0.15)` seconds between attempts. Each attempt opens a fresh session and transaction and re-checks lease ownership. Fetch, parse and process are not repeated. Other errors and `CancelledError` propagate at once.
3. **Clean up when retries run out** (`recovery.py:recover_failed_claim`, `f19c53b`): in a separate transaction, lock the target, close this job's attempts as failed, and call `fail_target()` only if the worker still owns the lease. If the database is down, lease expiry takes over, and it now counts the failure and backs off.
4. **Attempts carry their lease** (`d83a429ce034`), so recovery only closes attempts that belong to the expired lease.

Sorting removes the cycle that was observed in `crawl_target`; the retry covers cycles that sorting cannot rule out (documents, advisory locks); the recovery path makes sure a job that still fails leaves consistent state.

## Prevention
- Regression tests: `crawler/src/crawler/worker/tests/test_deadlock_retry.py` (eventual success, exhaustion, non-deadlock errors, cancellation), `worker/tests/test_postgres_pipeline.py` (concurrent claims and writes on Postgres).
- Monitoring: deadlock retries are logged at WARNING (`Database deadlock, retry n/4`) and exhaustion at ERROR. There is no counter or alert.
- Design change: none recorded as an ADR; the rules below are the design.
- Remaining risk: PR #4 added a global advisory lock (`lock_vocabulary()`) to every `_finalize()` (ADR-0002). That serializes all finalizations, which removes most cycles but costs throughput, and makes the lock order (advisory lock first, then rows) a new rule.

## Rules for future changes
- Any code that inserts or locks several rows in one transaction must do it in a sorted, deterministic order.
- Retry `40P01` only around a whole transaction that is safe to replay, never around a single statement, and never repeat network side effects inside the retry.
- A retried finalization must re-check lease ownership on each attempt.
- When a job fails after its attempt row exists, close that attempt (or leave it to lease-expiry recovery); never leave an attempt open with no owner.
- Keep passing: `worker/tests/test_deadlock_retry.py`, `worker/tests/test_postgres_pipeline.py`, `frontier/tests/`.

## References
- `crawler/src/crawler/test/upadte_log/update_10_20_2026_8_39_PM.md` (original long write-up)
- `crawler/src/crawler/test/update_log/06_deadlock_retry.md`, `08_failure_recovery.md`
