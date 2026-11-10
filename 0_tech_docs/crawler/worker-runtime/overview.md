# Worker lifecycle and recovery

Area: crawler · Status: active

## Purpose

Coordinates scheduling, one-target jobs, deadlines, attempts and replayable finalization. Network work occurs outside database transactions; a job is not one long transaction across the fetch.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/worker`](../../../crawler/src/crawler/worker)

## How-it-works docs

- [`crawler/src/crawler/worker/docs/jobs_docs.md`](../../../crawler/src/crawler/worker/docs/jobs_docs.md)
- [`crawler/src/crawler/worker/docs/runner_docs.md`](../../../crawler/src/crawler/worker/docs/runner_docs.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0004](../scheduler-and-leases/ADR-0004-postgres-frontier-as-job-queue-with-leases.md) | decision | PostgreSQL crawl_target table is the job queue, with time-boxed leases | accepted |
| [ADR-0020](ADR-0020-worker-transactions-and-recovery.md) | decision | Keep network I/O outside replayable lease-checked database transactions | accepted |
| [INC-0002](INC-0002-deadlocks-in-crawl-finalization.md) | incident | Multi-worker stress test deadlocked crawl finalization and left attempts unfinished | resolved |
| [INC-0011](INC-0011-abandoned-attempt-accounting.md) | incident | Expired jobs left unfinished attempts and bypassed failure backoff | resolved |
| [INC-0035](INC-0035-indexer-worker-exited-on-database-outage.md) | incident | Indexer worker exited for good when the database restarted | resolved |
| [EXP-0011](EXP-0011-database-outage-and-concurrent-writers.md) | experiment | Worker recovery from a real database restart, and crawler and indexer writers racing | done |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Keep resource outcome/parsing dispatch separate from lease-owned finalization;
  use the named transition, missing/noindex, and document-storage helpers (ADR-0054).

- Insert or lock several rows in one transaction only in a sorted, deterministic order (INC-0002).
- Retry `40P01` only around a whole replayable transaction, re-checking lease ownership each time, and never repeat network work (INC-0002).
- Never leave an attempt open with no owner; close it or leave it to lease recovery (INC-0002).
- Keep `claim_limit = min(batch_size, concurrency)` and `job_timeout_seconds <= lease_seconds - 15` (ADR-0004).
- Keep passing: `worker/tests/test_deadlock_retry.py`, `worker/tests/test_postgres_pipeline.py`.
- Keep runner policy separate from per-target processing.
- Preserve attempt lease ownership during recovery.
- Store the exact lease associated with every attempt.
- A stale worker may close its own old attempt but cannot requeue another owner claim.
