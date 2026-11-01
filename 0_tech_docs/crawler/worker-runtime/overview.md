# Worker runtime

Area: crawler · Status: active

## Purpose
Runs crawl jobs: `runner.py` claims a batch, runs each target through fetch, parse, process and one finalize transaction under a semaphore and a job timeout, and recovers leases. It owns how a single job behaves under failure (timeouts, deadlocks, crashes). It does not decide which URL comes next (`scheduler-and-leases`) or whether a URL is safe (`url-safety`).

## Code
- `crawler/src/crawler/worker/runner.py`
- `crawler/src/crawler/worker/jobs/`
- `crawler/src/crawler/worker/recovery.py`

## How-it-works docs
- `crawler/src/crawler/worker/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [INC-0002](INC-0002-deadlocks-in-crawl-finalization.md) | incident | Deadlocks in crawl finalization under several workers | resolved |
| [ADR-0004](../scheduler-and-leases/ADR-0004-postgres-frontier-as-job-queue-with-leases.md) | decision | Job queue and lease rules the runner follows (owned by scheduler-and-leases) | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] One target through the whole pipeline in one lease-safe transaction
- [x] Never claim more than the worker can start immediately (ADR-0004, INC-0002)
- [x] Job timeout at least 15 s under the lease; deadlock retry (ADR-0004, INC-0002)
- [x] Each attempt records its own lease so recovery closes only its attempts (ADR-0004, INC-0002)

## Rules for future changes
- Insert or lock several rows in one transaction only in a sorted, deterministic order (INC-0002).
- Retry `40P01` only around a whole replayable transaction, re-checking lease ownership each time, and never repeat network work (INC-0002).
- Never leave an attempt open with no owner; close it or leave it to lease recovery (INC-0002).
- Keep `claim_limit = min(batch_size, concurrency)` and `job_timeout_seconds <= lease_seconds - 15` (ADR-0004).
- Keep passing: `worker/tests/test_deadlock_retry.py`, `worker/tests/test_postgres_pipeline.py`.
