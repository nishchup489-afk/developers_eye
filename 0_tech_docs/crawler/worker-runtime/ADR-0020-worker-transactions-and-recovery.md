---
id: ADR-0020
title: Keep network I/O outside replayable lease-checked database transactions
status: accepted
date: '2026-11-02'
area: crawler
feature: worker-runtime
code:
- crawler/src/crawler/worker/runner.py
- crawler/src/crawler/worker/jobs/jobs.py
- crawler/src/crawler/worker/jobs/utility.py
- crawler/src/crawler/worker/recovery.py
supersedes: null
superseded_by: null
related:
- ADR-0004
- INC-0002
- INC-0011
---

# ADR-0020: Keep network I/O outside replayable lease-checked database transactions

## TL;DR

The runner owns scheduling and lifecycle; a job owns one target pipeline. Replay only database finalization when a deadlock occurs, with the lease guard checked again.

## Context

Long transactions across network requests hold locks needlessly. Expired leases and deadlock retries must not let an old worker overwrite a newer worker or repeat external fetches.

## Decision

Claim and attempt initialization are short transactions. Fetch, parse and processing occur outside them. Finalization persists content/links/outcome and transitions target state under lease ownership checks. Retry PostgreSQL 40P01 around the whole replayable transaction, not around one failed statement. Recover abandoned attempts by their recorded lease. Claim at most min(batch_size, concurrency), and enforce a job deadline at least 15 seconds inside the lease.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Short transactions plus lease fencing | Avoids locks during network waits | Needs explicit recovery boundaries | chosen |
| One transaction around the whole network pipeline | Superficially simple atomicity | Long-lived locks and failed transaction reuse | rejected |
| Retry the entire job on DB deadlock | Easy retry wrapper | Repeats network work and changes evidence | rejected |

## Why

The durable state transition is replayable; external network work is not part of that transaction. Separating them makes failures recoverable without pretending there is exactly-once fetching.

## Consequences

- Gained: Bounded ownership and recoverable interrupted attempts.
- Accepted limitations / tech debt: At-least-once acquisition can fetch a URL again after a crash; long-term exactly-once side effects are not promised.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- No network await occurs inside the claim/finalization transaction.
- Expired or replaced leases cannot finalize target state.
- Only a whole replayable transaction is retried after deadlock.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`crawler/src/crawler/worker/runner.py`](../../../crawler/src/crawler/worker/runner.py)
- [`crawler/src/crawler/worker/jobs/jobs.py`](../../../crawler/src/crawler/worker/jobs/jobs.py)
- [`crawler/src/crawler/worker/jobs/utility.py`](../../../crawler/src/crawler/worker/jobs/utility.py)
- [`crawler/src/crawler/worker/recovery.py`](../../../crawler/src/crawler/worker/recovery.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/src/crawler/worker/tests/test_deadlock_retry.py`](../../../crawler/src/crawler/worker/tests/test_deadlock_retry.py)
- [`crawler/src/crawler/worker/tests/test_postgres_pipeline.py`](../../../crawler/src/crawler/worker/tests/test_postgres_pipeline.py)

## Revisit when

- Job duration regularly approaches the lease deadline.
- Deadlock retry rates remain nonzero after ordering fixes.

## Rules for future changes

- Keep runner policy separate from per-target processing.
- Preserve attempt lease ownership during recovery.
