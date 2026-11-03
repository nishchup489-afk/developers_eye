# Scheduler and leases

Area: crawler · Status: active

## Purpose

Claims due work with target-row leases, source rotation and priority-before-depth ordering. This is best-effort round-robin fairness, not strict distributed FIFO or pure global BFS. Source-row claim locks were removed after the recorded concurrency benchmark.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/scheduler`](../../../crawler/src/crawler/scheduler)
- [`crawler/src/crawler/worker/recovery.py`](../../../crawler/src/crawler/worker/recovery.py)

## How-it-works docs

- [`crawler/src/crawler/scheduler/docs/REPOSITORY_README.md`](../../../crawler/src/crawler/scheduler/docs/REPOSITORY_README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0001](ADR-0001-round-robin-claims-without-source-locks.md) | decision | Round-robin claims without holding source row locks | accepted |
| [ADR-0004](ADR-0004-postgres-frontier-as-job-queue-with-leases.md) | decision | PostgreSQL crawl_target table is the job queue, with time-boxed leases | accepted |
| [ADR-0005](ADR-0005-round-robin-bfs-claim-order.md) | decision | Claim order is round robin across sources, then priority and BFS depth inside a source | accepted |
| [ADR-0006](ADR-0006-capped-exponential-retry-backoff.md) | decision | Failed targets retry with capped exponential backoff on failure_count, forever | accepted |
| [EXP-0001](EXP-0001-claim-path-concurrency-benchmark.md) | experiment | Claim path latency and multi-worker drain, source-locked vs unlocked round robin | done |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Do not lock `source` rows inside the `claim_targets()` loop (`FOR UPDATE`, with or without `SKIP LOCKED`) without a new ADR (ADR-0001).
- Keep the `flush()` after each lease and the ascending-id `last_claimed_at` update at the end of `claim_targets()` (ADR-0001).
- Do not go back to a single global priority order; keep `clock_timestamp()` and `GREATEST` for `last_claimed_at` (ADR-0005).
- Reset `failure_count` only in `complete_target()`; `Retry-After` may only lengthen a delay; permanent refusals are `block`, not `retry` (ADR-0006).
- Never start network work inside the claim transaction, and never hold a transaction open across a fetch (ADR-0004).
- Update a leased target only with the `lease_until = :expected AND lease_until > clock_timestamp()` guard (ADR-0004).
- Keep `job_timeout_seconds <= lease_seconds - 15` and `claim_limit = min(batch_size, concurrency)` (ADR-0004).
- Keep these passing: `scheduler/tests/test_concurrent_claims.py`, `scheduler/tests/test_round_robin.py`, `worker/tests/test_postgres_pipeline.py`.
