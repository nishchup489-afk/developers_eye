---
id: ADR-0001
title: Round-robin claims without holding source row locks
status: accepted
date: 2026-10-27
area: crawler
feature: scheduler-and-leases
code:
  - crawler/src/crawler/schedular/repository.py:claim_targets
supersedes:
superseded_by:
related: [EXP-0001]
---

# ADR-0001: Round-robin claims without holding source row locks

## TL;DR
`claim_targets()` reads the round-robin order of sources without locking them, claims targets with `FOR UPDATE SKIP LOCKED` on `crawl_target` only, and writes `source.last_claimed_at` once at the end, in source-id order. This lets several workers take different URLs from the same source at the same time. It keeps the round-robin fairness and needs no extra coordination tables or advisory locks.

## Context
Round-robin BFS claiming (commit `e019701`) fixed feed starvation: sources take turns by `source.last_claimed_at`, and inside a source the order is `priority DESC, depth ASC, next_fetch_at, id`.

That first version picked each source with `SELECT ... FOR UPDATE OF source SKIP LOCKED` and updated `last_claimed_at` inside the loop. Row locks last until the transaction ends, so the source row stayed locked for the whole claim transaction. A second worker claiming at the same moment skipped that source completely. When only one source had due work, the second worker got `[]` even though hundreds of URLs were waiting. The runner then sleeps `--poll-seconds` (10 s by default) before trying again.

`test_concurrent_claims_atomic_writes_and_shared_source_budget` caught it: two parallel claims on one source returned 2 and 0 targets instead of 2 and 2. EXP-0001 measured 6,528 empty claims with 4 workers and 12,066 with 8 while draining one source, and throughput fell as workers were added (136/s with 1 worker, 92/s with 4, 70/s with 8).

Constraints: keep atomic target claims and lease ownership, keep fairness across enabled and eligible sources, never claim the same URL twice, and don't add coordination machinery unless measurement shows it is needed.

## Decision
`claim_targets(session, limit, lease_seconds, source_id)` now does this:

1. **Read the order, don't lock it.** One query returns up to `limit` enabled sources that have a due, queued target, ordered `last_claimed_at ASC NULLS FIRST, id ASC`. There is no `FOR UPDATE` on `source`.
2. **Rotate in memory.** The source ids go into a queue. Take the source at the front and claim its best target with `SELECT ... FOR UPDATE OF crawl_target SKIP LOCKED LIMIT 1`. If a target comes back, lease it (`state = 'leased'`, `lease_until = clock_timestamp() + lease_seconds`), `flush()`, and put the source at the back of the queue. If no target comes back (nothing due, or every due target is locked by another worker), drop the source for this call.
3. **Fetch more sources only when needed.** If the queue runs empty and the last page was full, fetch the next page of sources, leaving out the ones already seen.
4. **Record turns at the end, in id order.** For each source that got a target, run `UPDATE source SET last_claimed_at = GREATEST(last_claimed_at, <time of its last claim in this call>)`, going through the sources in ascending `id` order.

The `flush()` after each lease is required. `SKIP LOCKED` only skips rows locked by *other* transactions, so without the flush the next query in the same call could return the target it has just leased.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Unlocked source order, target-only `SKIP LOCKED`, ordered `last_claimed_at` update at the end | Same queries per target as before; parallel claims on one source; no schema change | Two workers that claim at the same moment can both start with the same source; the second may wait a few ms for the first commit when it writes `last_claimed_at` | chosen |
| B. Keep `FOR UPDATE SKIP LOCKED` on the source row (the first version) | Strict one-worker-per-source turn | Second worker gets `[]` while work is left; throughput falls as workers are added (EXP-0001) | rejected: starves workers, fails the concurrency test |
| C. Lock the source with `FOR UPDATE` without `SKIP LOCKED` | No skipped sources | Every claim on a source runs one after the other; updating rows in loop order across sources can deadlock | rejected: serialises claims, risk of deadlock |
| D. Skip the `last_claimed_at` write if the row is locked (`SKIP LOCKED` on the update) | Never waits | A source can lose its turn mark and get extra turns; harder to reason about | rejected: weakens fairness for a few ms of waiting |
| E. Advisory locks or a separate "turn" table per source | Fine-grained control | More coordination to build, with no measured need once option A removes the source lock | rejected: not needed, see EXP-0001 |

## Why
- **Correctness.** A target can only be leased by the transaction that locked it with `SKIP LOCKED`, and the lease is only written in that transaction, so one URL is never claimed twice. Lease ownership is unchanged (`complete_target` and `fail_target` still check `lease_until`).
- **No deadlocks.** Claims never wait on `crawl_target` rows (they skip them). The only row locks that can make a claim wait are the `source` rows written in step 4, and every claim takes those in the same ascending-id order, so two claims can wait on each other but cannot form a cycle.
- **Fairness.** When claims run one after another, the order is the same as the first version: never-claimed sources first, then the one that waited longest, and inside one call the sources take turns (A B C A B A). `GREATEST` stops a claim that commits late from moving a source's turn mark backwards.
- **Performance.** Per claimed target there is still one target query plus a flush; the source order is read once per call instead of once per target, and `last_claimed_at` is written once per source instead of once per target. EXP-0001: one-source drain went from 92/s to 485/s with 4 workers and from 70/s to 563/s with 8, with zero empty claims while work was left.
- **Cost to build.** It changes one function, with no new tables, migrations or locks.

## Consequences
- Gained: several workers can claim from one busy source in parallel. The claim transaction holds no `source` row locks until the very end.
- Accepted limitations:
  - two workers claiming at the same moment read the same order and can both start with the same source. They take different targets, so this is only a small, temporary deviation from strict turn-taking;
  - a claim may wait on another claim's `source` row update until that transaction commits. The runner commits right after claiming, so the wait is milliseconds;
  - writing `last_claimed_at` takes a `FOR NO KEY UPDATE` row lock. It does not block inserting new `crawl_target` rows for that source, because the foreign key check only takes `FOR KEY SHARE`.
- What depends on this: `crawler/worker/runner.py` `claim_batch()` (one short transaction: `recover_expired_leases()`, then `claim_targets()`, then commit).

## Invariants
- `claim_targets()` never locks `source` rows before the final `last_claimed_at` update.
- Target selection always uses `FOR UPDATE OF crawl_target SKIP LOCKED`, and each lease is flushed before the next target query.
- `last_claimed_at` updates run in ascending `source.id` order and only move the value forward (`GREATEST`).
- Only enabled sources with a queued target due now are candidates. A source that gets no target keeps its `last_claimed_at`.

## Failure modes
- A worker crashes after claiming but before committing: the transaction rolls back, the target locks are released, and neither the leases nor `last_claimed_at` are saved.
- A claim transaction is held open for a long time by a caller: other claims that need to write the same source's `last_claimed_at` wait for it. `claim_batch()` keeps this transaction short; keep it that way.

## Evidence
- Measured: EXP-0001 (one source x 2000 targets and 50 sources x 40 targets, 1, 4 and 8 workers).
- Assumed: worker counts stay in the single digits per database, as in the runner's defaults.
- Tests:
  - `crawler/src/crawler/schedular/tests/test_concurrent_claims.py` (pytest, `TEST_DATABASE_URL`): overlapping claims on one source get different targets (3 + 3); overlapping claims on two sources each get one target per source; 4 parallel workers drain 1 x 60 and 6 x 10 targets with no duplicates and no empty claims while work is left. All four fail on the first version and pass now.
  - `crawler/src/crawler/worker/tests/test_postgres_pipeline.py::test_concurrent_claims_atomic_writes_and_shared_source_budget` passes again (2 and 2).
  - `crawler/src/crawler/schedular/tests/test_round_robin.py` still passes (21 checks), so the order when claims run one after another is unchanged.
- Commits: `e019701` (round-robin BFS with source locks); this change.

## Revisit when
- p95 `claim_targets(limit=10)` latency goes over 100 ms on production-sized data (EXP-0001 measured 57 to 89 ms with 50 sources on a dev container).
- more than about 16 concurrent workers share one database, or claims show up in `pg_stat_activity` waiting on `source` row locks.
- strict one-worker-per-source turn-taking becomes a requirement (for example per-host politeness enforced in the scheduler instead of `PolitenessManager`).

## Rules for future changes
- Do not add `FOR UPDATE` (with or without `SKIP LOCKED`) on `source` inside the claim loop without a new ADR.
- Keep the `flush()` after each lease and the ascending-id `last_claimed_at` update.
- Regression tests that must keep passing: `schedular/tests/test_concurrent_claims.py`, `schedular/tests/test_round_robin.py`, `schedular/tests/test_repository.py`, `worker/tests/test_postgres_pipeline.py`.
