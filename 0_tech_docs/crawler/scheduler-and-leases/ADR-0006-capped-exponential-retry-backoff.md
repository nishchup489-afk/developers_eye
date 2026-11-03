---
id: ADR-0006
title: Failed targets retry with capped exponential backoff on failure_count, forever
status: accepted
date: 2026-10-31
area: crawler
feature: scheduler-and-leases
code:
  - crawler/src/crawler/scheduler/repository.py:calculate_retry_delay
  - crawler/src/crawler/scheduler/repository.py:fail_target
  - crawler/src/crawler/scheduler/repository.py:complete_target
  - crawler/src/crawler/scheduler/repository.py:recover_expired_leases
  - crawler/src/crawler/worker/jobs/jobs.py
  - crawler/src/crawler/worker/jobs/utility.py:_finalize
  - crawler/src/crawler/worker/jobs/constants.py:_RETRY_AFTER_CAP_SECONDS
supersedes:
superseded_by:
related: [ADR-0004]
---

# ADR-0006: Capped exponential retry backoff on failure_count

## TL;DR
When a crawl fails in a way that might succeed later, the target goes back to `queued` with `failure_count + 1` and `next_fetch_at = now + min(60 s × 2^(failure_count − 1), 3600 s)`. A success resets `failure_count` to 0. A server's `Retry-After` can push the next attempt later, up to 24 h, but never earlier. Permanent refusals (robots deny, 401/403, out-of-scope redirect) are not retried at all; they move to `blocked`. There is no maximum retry count.

## Context
Before commit `f19c53b` (2026-10-20), a target whose lease expired was cleared and immediately due again, without counting the failure (see `0_tech_docs/journal/update-log/08_failure_recovery.md`). A URL that timed out or crashed the worker was retried as soon as the next claim ran, so one bad URL could take a worker slot over and over and hit the remote host every few seconds.

Constraints: be polite to hosts that are down or rate-limiting, keep transient failures (timeouts, 5xx, empty 200 bodies) cheap to recover from, and keep the rule simple enough to test.

## Decision
- **Which outcomes retry** (`process_job` in `worker/jobs/jobs.py`, action `retry`): a policy `DEFER` from `PolicyCoordinator.fetch()` (DNS lookup failure, robots.txt fetch failure, network error, HTTP 429/503 with `Retry-After` or the politeness default, HTTP 5xx), any other HTTP status other than 200, 204, 205, 304, 401, 403, 404 and 410, an HTTP 200 with an empty body, and any exception in fetch, parse or process.
- **Which outcomes do not retry**:
  - `complete` (normal recrawl interval): 200 parsed, 204/205, 304, 404/410 (the document is marked unavailable), 200 with an unsupported MIME type;
  - `block` (state `blocked`, never claimed again): robots `DENY`, 401/403, final URL outside the source's hosts or path scope;
  - `disable`: the source was disabled while the job ran.
- **Delay** (`calculate_retry_delay`): `min(base × 2^(n − 1), max)` with `base = 60 s`, `max = 3600 s`, where `n` is the new `failure_count`. That gives 1, 2, 4, 8, 16, 32 minutes, then 1 hour for every later failure. The exponent is capped at `max.bit_length()` so the integer stays small.
- **Retry-After.** If the response had `Retry-After`, `next_fetch_at = GREATEST(next_fetch_at, clock_timestamp() + min(retry_after, 86400 s))`. The server can only make us wait longer.
- **Expired lease counts as a failure.** `recover_expired_leases()` raises `failure_count` and applies the same delay.
- **Success resets.** `complete_target()` sets `failure_count = 0`.
- **No dead-letter state.** A target that keeps failing is retried once an hour indefinitely.

> **Question for nish:** why 60 s base and 1 h cap? Were they picked from somewhere (a crawler you read about, robots/politeness guidance), or a reasonable first guess? Also, is "retry forever" deliberate, or is a max failure count (then `state = 'failed'`) planned?

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Capped exponential backoff on `failure_count`, reset on success, `Retry-After` as a floor | Gentle on failing hosts; quick recovery from one-off errors; easy to test | No give-up; all failures back off the same way | chosen |
| B. Fixed retry delay | Simplest | Either too slow for blips or too aggressive for dead hosts | rejected |
| C. Immediate retry (the pre-`f19c53b` behaviour) | Fast recovery | A bad URL loops on a worker and hammers the host | rejected: caused the problem |
| D. Exponential with jitter | Spreads retries from many targets that failed together | Non-deterministic, harder to test; not needed at current scale | not done |
| E. Max attempts, then a `failed` / dead state | Stops wasting claims on dead URLs | Needs a way to revive them; risks dropping URLs after an outage | not done (see question) |

## Why
- **Politeness.** A host that is down or returning 5xx gets at most one request an hour per URL after six failures, and `Retry-After` is respected.
- **Reliability.** Transient errors recover within minutes; an outage of the worker's own network does not lose URLs because nothing is dropped.
- **Correctness.** The delay is written in the same guarded update that releases the lease (ADR-0004), so a stale worker cannot reschedule a target it no longer owns.
- **Cost to build.** One pure function plus one column that already existed.

## Consequences
- Gained: failing URLs stop monopolizing workers; failures are visible as `failure_count` in the admin monitor.
- Accepted limitations:
  - Permanently broken URLs (DNS gone, always 500) are retried hourly forever and stay in the frontier.
  - Backoff is per target, not per host. A host that is down for every URL still gets one attempt per URL per backoff step.
  - All targets that fail at the same moment come back at the same moment (no jitter).
  - `fail_target()` and `complete_target()` compute `next_fetch_at` from `now()` (transaction start), while lease checks use `clock_timestamp()`. The difference is the length of the finalize transaction, so it is harmless.
- What depends on this: the claim filter `next_fetch_at <= now()` (ADR-0005) and the lease recovery path (ADR-0004).

## Invariants
- `calculate_retry_delay(n)` is in `[base, max]` and non-decreasing in `n`; it rejects `n <= 0`.
- `failure_count` only goes up on retry or lease expiry and only goes back to 0 on `complete`.
- `Retry-After` never moves `next_fetch_at` earlier and is capped at 86,400 s.
- `block` and `disable` never schedule a retry.

## Evidence
- Tests: `scheduler/tests/test_repository.py` (delay values, cap, `fail_target` ownership), worker offline tests for timeout accounting and expired-lease backoff (see `08_failure_recovery.md`).
- Measured: none.
- Commits: `90e9ef3` (scheduler functions), `f19c53b` (backoff on abandoned attempts and expired leases).

## Revisit when
- The frontier carries many targets with `failure_count >= 7` (permanently at the hourly cap); add a give-up state (option E).
- One host's outage shows up as hundreds of hourly retries; add per-host backoff.
- Many targets fail together (an outage) and their synchronized return causes a burst; add jitter (option D).

## Rules for future changes
- Change base or cap only in `calculate_retry_delay()` defaults, and update the delay tests.
- Never reset `failure_count` anywhere except `complete_target()`.
- Do not let `Retry-After` shorten a delay.
- Do not add a new retryable outcome without deciding whether it is `retry` or `block`; a permanent refusal must be `block`.
- Keep passing: `scheduler/tests/test_repository.py`, `worker/tests/` offline suite.
