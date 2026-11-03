---
id: INC-0011
title: Expired jobs left unfinished attempts and bypassed failure backoff
status: resolved
date: '2026-11-02'
severity: high
area: crawler
feature: worker-runtime
code:
- crawler/src/crawler/worker/recovery.py
- crawler/src/crawler/worker/jobs/jobs.py
- crawler/src/crawler/scheduler/repository.py
- backend/src/backend/models/crawl_attempt.py
fix_commits:
- f19c53beec6ba5b152d09c64a503f13e45a447a2
related:
- ADR-0004
- ADR-0020
---

# INC-0011: Expired jobs left unfinished attempts and bypassed failure backoff

## Signature

A timeout could remain unfinished while its target immediately retried after lease expiration.

## Summary

Crashes, timeouts and exhausted storage retries previously left attempt records open. Clearing a target lease without normal failure accounting caused immediate retries and misleading monitoring.

## Expected vs actual

- Expected: Recovery closes the attempt belonging to the expired lease and schedules the normal failure delay without touching a newer claim.
- Actual: Attempt closure and retry accounting were missing from some failure/recovery paths.

## Root cause

The attempt lacked a durable link to its exact frontier lease, and recovery did not consistently reuse scheduler failure semantics.

## Fixes that did not work

No additional failed repair attempt is established by the cited evidence. Do not infer one from the desired outcome.

## Resolution

Persist the attempt lease token; close failed jobs in an independent transaction, apply guarded scheduler backoff, close expired-lease attempts, reconcile historical unfinished attempts only without a live owner, and protect terminal telemetry from late checkpoints. If the database is down, lease recovery retries after connectivity returns.

## Prevention

- Regression test: timeout accounting, expired lease backoff and newer-claim preservation.
- Database test: overlap recovery and a stale worker finalization.
- Remaining risk: recovery depends on database availability and a running recovery loop.

## Rules for future changes

- Store the exact lease associated with every attempt.
- A stale worker may close its own old attempt but cannot requeue another owner claim.

## Evidence

[Historical recovery log](../../journal/update-log/08_failure_recovery.md) and its linked regression suites.

- [`crawler/src/crawler/worker/recovery.py`](../../../crawler/src/crawler/worker/recovery.py)
- [`crawler/src/crawler/worker/jobs/jobs.py`](../../../crawler/src/crawler/worker/jobs/jobs.py)
- [`crawler/src/crawler/scheduler/repository.py`](../../../crawler/src/crawler/scheduler/repository.py)
- [`backend/src/backend/models/crawl_attempt.py`](../../../backend/src/backend/models/crawl_attempt.py)
