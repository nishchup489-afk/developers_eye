# Admin console and server proxy

Area: frontend · Status: active

## Purpose

The crawler, indexer, vocabulary, corpus and availability views consume backend-owned read-only reports. Server routes validate session, configuration and response shape; browser code never receives the shared service key.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`frontend/components/admin`](../../../frontend/components/admin)
- [`frontend/app/api/admin`](../../../frontend/app/api/admin)
- [`frontend/lib/crawler-proxy.ts`](../../../frontend/lib/crawler-proxy.ts)
- [`frontend/lib/axios.js`](../../../frontend/lib/axios.js)

## How-it-works docs

- [`frontend/tests/test_case.md`](../../../frontend/tests/test_case.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0030](../../backend/admin-api/ADR-0030-read-only-observability-plane.md) | decision | Expose read-only operational reports from backend-owned query services | accepted |
| [ADR-0032](../admin-auth/ADR-0032-github-admin-auth-and-service-key-boundary.md) | decision | Authenticate admins with GitHub and keep the backend key behind server routes | accepted |
| [ADR-0037](../../indexer/coverage-reporting/ADR-0037-operational-coverage-snapshot-semantics.md) | decision | Treat coverage and vocabulary reports as operational observations | accepted |
| [ADR-0044](../../backend/admin-api/ADR-0044-search-availability-telemetry.md) | decision | Record search outcomes per minute in PostgreSQL, and sample the corpus for statistics | accepted |
| [ADR-0057](../../backend/admin-api/ADR-0057-slow-search-log-and-human-judging.md) | decision | Log slow searches with stage timings and store human relevance judgments in PostgreSQL | accepted |
| [INC-0043](INC-0043-slow-search-tab-rejected-empty-window.md) | incident | Slow searches tab rejected an empty window as invalid data | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- HTTP goes through axios, not raw `fetch`: browser components use `api` and server routes use `backend` / `adminGet`, all from `lib/axios.js`; `backend` keeps the fetch adapter, `cache: "no-store"`, `redirect: "error"` and the timeouts. Both clients resolve every status, so check `response.status` and map errors yourself.
- Separate operational write commands into a new design and permission model.
- Keep secrets server-side and report status meanings explicit.
- Keep OAuth state/PKCE and signed-cookie checks covered by regression tests.
- Rotate exposed credentials; deleting a tracked file alone is not remediation.
- Label snapshot limitations and keep report queries read-only.
- Use a dedicated reconciliation/query plan for correctness checks.
