# Backend and worker package boundary

Area: backend · Status: active

## Purpose

Crawler/indexer depend on the relative backend package for shared models and sessions. API/report query code belongs to backend/admin_services, so serving the API does not import the worker runtime.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`backend/src/backend/admin_services`](../../../backend/src/backend/admin_services)

## How-it-works docs

- [`backend/README.md`](../../../backend/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0012](ADR-0012-crawler-depends-on-backend-never-reverse.md) | decision | The crawler package depends on the backend package, never the reverse | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Keep the current shared backend package until the extraction gate in ADR-0054
  is met; crawler finalization must not import indexer mutation helpers.

- Never import `crawler` or `indexer` from `backend`; move shared code into `backend` (ADR-0012).
- Keep path dependencies relative (ADR-0012).
- Keep passing: `backend/tests/test_package_boundary.py`.
