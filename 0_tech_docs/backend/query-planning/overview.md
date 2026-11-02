# Query analysis and explicit retrieval planning

Area: backend · Status: active

## Purpose

Pure analyzer and planner components are implemented, but the public route still performs its earlier normalization. No automatic code-intent model or complete query-router orchestration is delivered.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/query_analyzer`](../../../backend/src/backend/search/query_analyzer)
- [`backend/src/backend/search/query_selector`](../../../backend/src/backend/search/query_selector)
- [`backend/src/backend/search/config.py`](../../../backend/src/backend/search/config.py)

## How-it-works docs

- [`backend/tests/test_case.md`](../../../backend/tests/test_case.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0023](ADR-0023-pure-query-analysis-and-explicit-planning.md) | decision | Keep query normalization and retrieval planning pure and explicit | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Reconcile the frontend, route and analyzer contracts in one integration change.
- Do not call the query analyzer a PostgreSQL tokenizer.
