# Public API documentation page

Area: frontend · Status: active

## Purpose

Explains caller-visible routes and live/demo contracts. Public documentation is a maintained presentation of the schema; it is not automatic evidence that a proposed backend pipeline is complete.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`frontend/app/docs/page.tsx`](../../../frontend/app/docs/page.tsx)
- [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md)
- [`backend/src/backend/schema/search.py`](../../../backend/src/backend/schema/search.py)

## How-it-works docs

- [`api-map.md`](../../infra/system-architecture/api-map.md): generated route map (Next.js and FastAPI) that the public reference should agree with
- [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0031](../search-experience/ADR-0031-same-origin-search-and-explicit-demo.md) | decision | Use a validated same-origin search bridge with explicit demo mode | accepted |
| [ADR-0034](../../infra/docs-navigation/ADR-0034-two-documentation-layers-and-navigation.md) | decision | Keep mechanics separate from decision history and generate shared navigation | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Change backend response schemas and frontend validators together.
- Keep timeout, no-store and redirect behavior when changing the HTTP abstraction.
- Do not rewrite accepted rationale to invent history.
- Update public API documentation and validators with contract changes.
- Use the generator for generated navigation blocks.
