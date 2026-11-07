# Read-only admin API

Area: backend · Status: active

## Purpose

Returns operational reports and inspections behind the shared bearer key. It is a visibility plane and does not expose worker control or destructive operations.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/api/crawler_report.py`](../../../backend/src/backend/api/crawler_report.py)
- [`backend/src/backend/api/indexer_report.py`](../../../backend/src/backend/api/indexer_report.py)
- [`backend/src/backend/admin_services`](../../../backend/src/backend/admin_services)
- [`backend/src/backend/search/telemetry.py`](../../../backend/src/backend/search/telemetry.py)

## How-it-works docs

- [`backend/README.md`](../../../backend/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0030](ADR-0030-read-only-observability-plane.md) | decision | Expose read-only operational reports from backend-owned query services | accepted |
| [ADR-0044](ADR-0044-search-availability-telemetry.md) | decision | Record search outcomes per minute in PostgreSQL, and sample the corpus for statistics | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Separate operational write commands into a new design and permission model.
- Keep secrets server-side and report status meanings explicit.
