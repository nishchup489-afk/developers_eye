---
id: INC-0035
title: Indexer worker exited for good when the database restarted
status: resolved
date: '2026-11-08'
severity: medium
area: indexer
feature: worker-runtime
code:
- crawler/src/indexer/worker/runner.py
- crawler/src/crawler/worker/runner.py
- backend/src/backend/db/session.py
- backend/src/backend/api/search.py
fix_commits:
- 7c0ee7a
- dc185f8
- 2e71bf1
- 489b5cc
related:
- EXP-0011
- ADR-0020
---

# INC-0035: Indexer worker exited for good when the database restarted

## Signature

```
sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) connection was closed in the middle of operation
```

The indexer process then stops, with this as its last log line.

## Summary

Found by stopping a throwaway Postgres under the running workers (EXP-0011). `indexer.worker.runner.run_worker --forever` had no handling around candidate selection, so one lost connection ended the process and 1,620 outdated documents stayed outdated after the server came back. Nothing was corrupted. In the deploy stack `restart: unless-stopped` would restart the container, but outside Docker indexing simply stops. No real outage happened.

## Expected vs actual

- Expected: workers wait out a database restart and carry on.
- Actual: the crawler did, the indexer did not.

## Root cause

`run_batch` selects candidates before it starts its per-document error handling, and `run_worker` only had try/finally around it.

Two smaller gaps came from the same review. The crawler's claim loop did not catch SQLAlchemy's pool `TimeoutError`, which is not a DBAPIError, so an exhausted pool would have ended the worker. The search route only caught `SQLAlchemyError`, but a refused connection surfaces as a plain `ConnectionRefusedError`, so a stopped database answered 500 instead of 503.

## Fixes that did not work

| Attempt | Why it failed |
| --- | --- |
| Listing asyncpg's error types in the shared tuple (7c0ee7a) | Unnecessary. On SQLAlchemy 2.1 they arrive wrapped as DBAPIError during a real restart. Removed in 489b5cc |

## Resolution

`DATABASE_UNAVAILABLE_ERRORS` in `backend/db/session.py` names what an outage looks like: DBAPIError, pool timeout, OSError. The crawler claim loop, lease reaper, indexer loop, vocabulary drain and search routes all use it. The indexer keeps its cursors and retries every 5 seconds. One-shot mode still reports the failure.

## Prevention

- Regression test: `crawler/tests/indexer/test_worker_recovery.py`, `crawler/tests/crawler/worker/test_runner_continuous.py`, `backend/tests/api/test_search_route.py`.
- Monitoring / alert: the admin indexer heartbeat already shows a stopped worker.
- Design change (ADR): none. ADR-0020 already relies on lease expiry for recovery.
- Remaining risk: worker startup still exits if the database is down, and relies on the process manager to restart it.

## Rules for future changes

- A polling loop must catch `DATABASE_UNAVAILABLE_ERRORS`, wait and continue.
- Test outage handling by really stopping a server. Mocks only prove the error types you thought of.
