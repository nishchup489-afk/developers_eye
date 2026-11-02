# System architecture and implementation status

Area: infra · Status: active

## Purpose

Four independently started processes share PostgreSQL. The current public API serves stored FTS results; the modular search path is partially implemented. Read architecture.md for the actual data flow, storage ownership and integration gaps.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend`](../../../backend/src/backend)
- [`crawler/src/crawler`](../../../crawler/src/crawler)
- [`crawler/src/indexer`](../../../crawler/src/indexer)
- [`frontend`](../../../frontend)

## How-it-works docs

- [`technical_handoff.md`](../../../technical_handoff.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0013](ADR-0013-offline-online-process-boundaries.md) | decision | Separate acquisition, indexing, and query serving around PostgreSQL | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Keep acquisition and indexing outside the search request.
- Update the architecture status table before claiming a planned component is live.
