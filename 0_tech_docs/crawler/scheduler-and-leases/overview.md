# Scheduler and leases

Area: crawler · Status: active

## Purpose
Hands out crawl work. `crawl_target` is both the URL frontier and the job queue: workers claim due rows with leases, then complete or fail them, and expired leases are put back in the queue. This feature decides which URL is fetched next and protects against two workers fetching the same URL. It does not fetch, parse or decide crawl scope (see `url-frontier`, `worker-runtime`).

## Code
- `crawler/src/crawler/schedular/`

## How-it-works docs
- `crawler/src/crawler/schedular/DOCS/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0001](ADR-0001-round-robin-claims-without-source-locks.md) | decision | Round-robin claims without holding source row locks | accepted |
| [EXP-0001](EXP-0001-claim-path-concurrency-benchmark.md) | experiment | Claim path latency and multi-worker drain | done, adopt |
| [ADR-0004](ADR-0004-postgres-frontier-as-job-queue-with-leases.md) | decision | PostgreSQL crawl_target table is the job queue, with time-boxed leases | accepted |
| [ADR-0005](ADR-0005-round-robin-bfs-claim-order.md) | decision | Round robin across sources, then priority and BFS depth inside a source | accepted |
| [ADR-0006](ADR-0006-capped-exponential-retry-backoff.md) | decision | Capped exponential retry backoff on failure_count | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] PostgreSQL as the job queue instead of an external broker (ADR-0004)
- [x] Claim ordering `priority DESC, next_fetch_at, id` with `FOR UPDATE SKIP LOCKED` (see `crawler/faced_problems.md`), replaced by round-robin BFS below (recorded as option B in ADR-0005)
- [x] Round-robin BFS claiming to stop feed starvation: sources take turns by `source.last_claimed_at`, and inside a source `priority DESC, depth ASC` (ADR-0005)
- [x] Claim concurrently without holding source row locks (ADR-0001, EXP-0001)
- [x] Exponential backoff with `failure_count` (ADR-0006)
- [x] Lease recovery for expired leases (ADR-0004)

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._

- Do not lock `source` rows inside the `claim_targets()` loop (`FOR UPDATE`, with or without `SKIP LOCKED`) without a new ADR (ADR-0001).
- Keep the `flush()` after each lease and the ascending-id `last_claimed_at` update at the end of `claim_targets()` (ADR-0001).
- Do not go back to a single global priority order; keep `clock_timestamp()` and `GREATEST` for `last_claimed_at` (ADR-0005).
- Reset `failure_count` only in `complete_target()`; `Retry-After` may only lengthen a delay; permanent refusals are `block`, not `retry` (ADR-0006).
- Never start network work inside the claim transaction, and never hold a transaction open across a fetch (ADR-0004).
- Update a leased target only with the `lease_until = :expected AND lease_until > clock_timestamp()` guard (ADR-0004).
- Keep `job_timeout_seconds <= lease_seconds - 15` and `claim_limit = min(batch_size, concurrency)` (ADR-0004).
- Keep these passing: `schedular/tests/test_concurrent_claims.py`, `schedular/tests/test_round_robin.py`, `worker/tests/test_postgres_pipeline.py`.
