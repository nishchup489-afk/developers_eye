# Scheduler and leases

Area: crawler · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/crawler/schedular/`

## How-it-works docs
- `crawler/src/crawler/schedular/DOCS/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0001](ADR-0001-round-robin-claims-without-source-locks.md) | decision | Round-robin claims without holding source row locks | accepted |
| [EXP-0001](EXP-0001-claim-path-concurrency-benchmark.md) | experiment | Claim path latency and multi-worker drain | done, adopt |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] PostgreSQL as the job queue instead of an external broker
- [ ] Claim ordering `priority DESC, next_fetch_at, id` with `FOR UPDATE SKIP LOCKED` (see `crawler/faced_problems.md`), replaced by round-robin BFS below
- [ ] Round-robin BFS claiming to stop feed starvation: sources take turns by `source.last_claimed_at`, and inside a source `priority DESC, depth ASC` (see `DOCS/REPOSITORY_README.md`)
- [x] Claim concurrently without holding source row locks (ADR-0001, EXP-0001)
- [ ] Exponential backoff with `failure_count`
- [ ] Lease recovery for expired leases

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._

- Do not lock `source` rows inside the `claim_targets()` loop (`FOR UPDATE`, with or without `SKIP LOCKED`) without a new ADR (ADR-0001).
- Keep the `flush()` after each lease and the ascending-id `last_claimed_at` update at the end of `claim_targets()` (ADR-0001).
- Keep these passing: `schedular/tests/test_concurrent_claims.py`, `schedular/tests/test_round_robin.py`, `worker/tests/test_postgres_pipeline.py`.
