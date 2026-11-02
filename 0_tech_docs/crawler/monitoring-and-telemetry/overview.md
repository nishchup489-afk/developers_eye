# Crawler telemetry

Area: crawler · Status: active

## Purpose

Persists stage events and worker heartbeats and exposes them through backend-owned read-only reports. Event volume and retention need measurement; heartbeat presence does not prove successful crawl progress.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/worker/telemetry.py`](../../../crawler/src/crawler/worker/telemetry.py)
- [`backend/src/backend/models/crawl_monitor.py`](../../../backend/src/backend/models/crawl_monitor.py)
- [`backend/src/backend/admin_services`](../../../backend/src/backend/admin_services)

## How-it-works docs

- [`crawler/src/crawler/worker/tests/README.md`](../../../crawler/src/crawler/worker/tests/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0030](../../backend/admin-api/ADR-0030-read-only-observability-plane.md) | decision | Expose read-only operational reports from backend-owned query services | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Separate operational write commands into a new design and permission model.
- Keep secrets server-side and report status meanings explicit.
