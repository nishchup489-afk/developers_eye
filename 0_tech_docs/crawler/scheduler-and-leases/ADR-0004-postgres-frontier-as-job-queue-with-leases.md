---
id: ADR-0004
title: PostgreSQL crawl_target table is the job queue, with time-boxed leases
status: accepted
date: 2026-10-31
area: crawler
feature: scheduler-and-leases
code:
  - crawler/src/crawler/schedular/repository.py:claim_targets
  - crawler/src/crawler/schedular/repository.py:complete_target
  - crawler/src/crawler/schedular/repository.py:fail_target
  - crawler/src/crawler/schedular/repository.py:recover_expired_leases
  - crawler/src/crawler/worker/runner.py:claim_batch
  - crawler/src/crawler/worker/runner.py:RunnerConfig
  - crawler/src/crawler/worker/recovery.py:recover_failed_claim
  - crawler/src/crawler/writer/attempts.py:close_abandoned_attempts
  - backend/src/backend/models/crawler_frontier.py
supersedes:
superseded_by:
related: [ADR-0001, ADR-0005, ADR-0006]
---

# ADR-0004: PostgreSQL crawl_target table is the job queue, with time-boxed leases

## TL;DR
There is no message broker. The URL frontier table `crawl_target` is the queue: a worker claims due rows with `FOR UPDATE SKIP LOCKED`, sets `state = 'leased'` and `lease_until = clock_timestamp() + lease_seconds`, and commits right away. Finishing or failing a target only succeeds if the row still carries the exact `lease_until` the worker was given. Leases that run out are put back in the queue by the next claim. One database gives us durability, ordering and crash recovery with no extra service.

## Context
The crawler already stored every URL in PostgreSQL (`crawl_target`: `state`, `priority`, `depth`, `next_fetch_at`, `failure_count`) because the frontier needs deduplication by `normalized_url`, per-source budgets and scheduling by `next_fetch_at`. The question was where the "work to do now" queue should live.

Constraints:
- One developer, running everything locally on Windows; every extra service is something to install and keep running.
- Workers can crash or be killed mid-fetch; a URL must not be lost or stuck forever.
- Several workers (processes and asyncio tasks) must never fetch the same URL at the same time.
- A fetch takes seconds, not milliseconds; throughput needs are tens to hundreds of URLs per second, not thousands.

> **Question for nish:** did you consider Redis/RQ, Celery or RabbitMQ before building this? If so, what decided it (setup on Windows, keeping one source of truth, learning goal)? Add a line to the options table.

## Decision
- **Claim** (`claim_batch` → `claim_targets`): in one short transaction, `recover_expired_leases()` then `claim_targets(limit = min(batch_size, concurrency), lease_seconds)`, then commit. Rows are picked with `FOR UPDATE OF crawl_target SKIP LOCKED` among `state = 'queued' AND next_fetch_at <= now()` (order: ADR-0005; locking: ADR-0001). Each claimed row gets `state = 'leased'`, `lease_until = clock_timestamp() + lease_seconds`. Rows are copied to Pydantic read models before the session closes; all network work happens after the commit.
- **Lease as ownership token.** `complete_target()` and `fail_target()` update the row only `WHERE state = 'leased' AND lease_until = :expected_lease_until AND lease_until > clock_timestamp()`. If that matches nothing, the worker has lost the target (it expired and someone else may have it) and must not write the outcome.
- **Complete** → `state = 'queued'`, `lease_until = NULL`, `failure_count = 0`, `next_fetch_at` moved forward by the recrawl interval.
- **Fail** → `state = 'queued'`, `lease_until = NULL`, `failure_count + 1`, `next_fetch_at = now + backoff` (ADR-0006).
- **Expired leases** (`recover_expired_leases`): up to 500 rows with `state = 'leased' AND (lease_until <= clock_timestamp() OR lease_until IS NULL)`, locked `SKIP LOCKED`, are requeued with `failure_count + 1` and backoff. Their open `crawl_attempt` rows are closed as `lease_expired`. Targets that are not leased but still have an unfinished attempt get that attempt closed as abandoned.
- **Attempts carry the lease.** Each `crawl_attempt` stores the `lease_until` it ran under (migration `d83a429ce034`), so recovery closes only the attempts of the lease that expired, not a newer attempt by another worker.
- **Timing rules** (`RunnerConfig`): `lease_seconds >= 30` (default 300), `job_timeout_seconds <= lease_seconds - 15` (default 240), and a worker never claims more targets than it can start immediately.
- **Failed claim cleanup** (`recover_failed_claim`): if a job crashes, the worker locks the target, closes its own attempts and calls `fail_target()` only if it still owns the lease. If the database is down, it leaves the row for lease expiry.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. `crawl_target` as the queue, `SKIP LOCKED` claims, leases, recovery on claim | One source of truth; claims and frontier writes are transactional; nothing else to run; state is visible with SQL | Polling (`--poll-seconds`); claim queries load the database; we own the recovery logic | chosen |
| B. External broker (Redis/RQ, Celery + RabbitMQ) holding URLs | Push delivery, built-in retries, mature tooling | Two stores that must agree (frontier in Postgres, queue in the broker); another service on Windows; enqueue and frontier insert are not atomic | rejected |
| C. Claim with `FOR UPDATE` (no `SKIP LOCKED`) | Simple | Workers queue behind each other on the same rows | rejected |
| D. Hold the row lock for the whole fetch instead of a lease | No expiry logic | Long transactions; a crash or hung connection holds the lock; ties a DB connection to each fetch | rejected |
| E. Advisory locks keyed by target id | No schema change | Locks are tied to sessions, not visible in the table, and lost on reconnect | rejected |

## Why
- **Correctness.** `SKIP LOCKED` plus the lease write in the same transaction means two workers cannot lease the same row. Checking the exact `lease_until` on finish means a worker whose lease expired cannot overwrite the result of the worker that took over.
- **Reliability.** A crashed worker loses nothing: its rows come back after `lease_seconds`, with `failure_count` raised so a URL that kills workers backs off instead of looping.
- **Operability.** Queue depth, stuck leases and retries are plain SQL queries and show up in the admin monitor.
- **Cost to build.** No new infrastructure; the claim, complete, fail and recover functions are in one file.

## Consequences
- Gained: crash-safe work distribution with one database; frontier inserts (child links) and target completion commit together in `_finalize`.
- Accepted limitations:
  - Workers poll. An empty claim sleeps `--poll-seconds` (10 s), so new work can wait up to that long.
  - A worker that dies holds its targets until the lease runs out (5 minutes by default).
  - Recovery only runs when some worker claims. With no workers running, expired leases stay `leased`.
  - Recovery handles 500 expired rows per claim.
- What depends on this: the worker runtime (one target per job, job timeout under the lease), the admin monitor (reads `state` and `lease_until`), and every frontier test.

## Invariants
- A target is leased only inside a transaction that locked it with `FOR UPDATE ... SKIP LOCKED`.
- The claim transaction commits before any fetch starts.
- `complete_target()` and `fail_target()` write only when `lease_until` equals the value the worker received and is still in the future.
- `job_timeout_seconds <= lease_seconds - 15` and `lease_seconds >= 30`.
- A worker claims at most `concurrency` targets per call.
- Every `crawl_attempt` row records the `lease_until` it ran under; recovery closes attempts by that value.

## Failure modes
- Worker killed mid-job: lease expires, the next claim requeues the row with backoff and closes the attempt as `lease_expired`.
- Clock: all lease times use the database's `clock_timestamp()`, never the worker's clock, so client clock skew does not matter.
- Job runs past its lease despite the timeout (blocked event loop): another worker may claim and fetch the same URL. The first worker's `complete_target()` then matches nothing and its result is dropped. Duplicate fetches are possible; duplicate writes of the target state are not.
- Real incidents in this area: deadlocks during finalization and abandoned attempts (see `crawler/src/crawler/test/update_log/06_deadlock_retry.md`, `08_failure_recovery.md`).

## Evidence
- Tests: `schedular/tests/test_repository.py`, `schedular/tests/test_concurrent_claims.py`, `worker/tests/test_postgres_pipeline.py` (concurrent claims, lease ownership, recovery).
- Measured: EXP-0001 (claim latency 39 to 115 ms p50 to p95 for `limit=10`; up to about 570 targets/s claimed with 8 workers on one source).
- Assumed: single-digit worker counts per database.
- Commits: `4cc31cc` (claim), `ec80e89` (complete), `90e9ef3` (all scheduler functions), `f19c53b` (abandoned attempts and safe backoff), `d83a429ce034` migration (attempt leases).

## Revisit when
- Claims are a visible share of database load, or `claim_targets` p95 goes over 100 ms.
- Polling delay matters (for example, near-real-time recrawl of feeds); consider `LISTEN/NOTIFY` to wake workers.
- Workers run on more than one machine against one database and connection count becomes the limit.
- Throughput needs go beyond what one Postgres primary can claim (thousands of targets per second).

## Rules for future changes
- Never start network work inside the claim transaction.
- Never update a leased target without the `lease_until = :expected AND lease_until > clock_timestamp()` guard.
- Use `clock_timestamp()` for lease times, not `now()` and not Python's clock.
- Keep `job_timeout_seconds` at least 15 s under `lease_seconds`, and keep `claim_limit = min(batch_size, concurrency)`.
- Do not hold a database transaction open across a fetch.
- Keep passing: `schedular/tests/test_repository.py`, `schedular/tests/test_concurrent_claims.py`, `worker/tests/test_postgres_pipeline.py`.
