---
id: ADR-0030
title: Expose read-only operational reports from backend-owned query services
status: accepted
date: '2026-11-02'
area: backend
feature: admin-api
code:
- backend/src/backend/api/crawler_report.py
- backend/src/backend/api/indexer_report.py
- backend/src/backend/admin_services
- backend/src/backend/models/crawl_monitor.py
- crawler/src/crawler/worker/telemetry.py
supersedes: null
superseded_by: null
related:
- ADR-0012
- ADR-0032
- ADR-0037
---

# ADR-0030: Expose read-only operational reports from backend-owned query services

## TL;DR

Keep admin APIs read-only and put their database query services in backend. Persist crawler stage events and heartbeats so operational state survives a terminal session.

## Context

The crawler and indexer need inspectable progress and failure evidence, while the API package must remain importable without crawler internals. The dashboard currently has no operational write-control contract.

## Decision

Backend serves crawler report/monitor/document/attempt details, indexer coverage, and vocabulary reporting. Admin routes share CRAWLER_REPORT_API_KEY bearer authentication. Crawler telemetry records stage events and worker heartbeats in PostgreSQL; reporting helpers in the crawler delegate to backend services. Next.js validates admin sessions and upstream payloads. Reports are observations; they cannot start workers, cancel jobs or delete content.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Backend-owned read-only services | Clear dependency direction and narrow authority | Extra queries and event storage | chosen |
| Import worker modules into the API | Quick reuse | Circular package dependencies and runtime coupling | rejected |
| Add control buttons before command semantics | Convenient UI | Unspecified auth, replay and job ownership | deferred |

## Why

Read-only visibility has different failure and authorization requirements from worker control. Persisted telemetry helps distinguish leased work, stale workers and actual completed attempts.

## Consequences

- Gained: Operators can inspect state without granting mutation access.
- Accepted limitations / tech debt: Telemetry adds database writes and needs retention; heartbeat freshness is a liveness hint, not proof of useful progress.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Backend never imports crawler/indexer modules.
- Every admin backend endpoint authenticates the service key.
- Reports cannot mutate crawl/index state.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/src/backend/api/crawler_report.py`](../../../backend/src/backend/api/crawler_report.py)
- [`backend/src/backend/api/indexer_report.py`](../../../backend/src/backend/api/indexer_report.py)
- [`backend/src/backend/admin_services`](../../../backend/src/backend/admin_services)
- [`backend/src/backend/models/crawl_monitor.py`](../../../backend/src/backend/models/crawl_monitor.py)
- [`crawler/src/crawler/worker/telemetry.py`](../../../crawler/src/crawler/worker/telemetry.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/tests/test_package_boundary.py`](../../../backend/tests/test_package_boundary.py)
- [`frontend/tests/admin-routes.mjs`](../../../frontend/tests/admin-routes.mjs)
- [`crawler/src/crawler/worker/tests/test_monitoring.py`](../../../crawler/src/crawler/worker/tests/test_monitoring.py)

## Revisit when

- Before any administrative mutation endpoint is introduced.
- Telemetry retention or report queries materially burden the primary database.

## Rules for future changes

- Separate operational write commands into a new design and permission model.
- Keep secrets server-side and report status meanings explicit.
