# Index and vocabulary coverage reporting

Area: indexer · Status: active

## Purpose

Describes index coverage/version freshness and current vocabulary observations. Reports do not verify exact frequency reconciliation, quality, or a single consistent cross-query snapshot.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/admin_services/indexer_reporting.py`](../../../backend/src/backend/admin_services/indexer_reporting.py)
- [`backend/src/backend/admin_services/vocabulary_reporting.py`](../../../backend/src/backend/admin_services/vocabulary_reporting.py)
- [`crawler/src/indexer/reporting.py`](../../../crawler/src/indexer/reporting.py)

## How-it-works docs

- [`crawler/src/indexer/docs/reporting.md`](../../../crawler/src/indexer/docs/reporting.md)
- [`crawler/src/indexer/operations.md`](../../../crawler/src/indexer/operations.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0037](ADR-0037-operational-coverage-snapshot-semantics.md) | decision | Treat coverage and vocabulary reports as operational observations | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Label snapshot limitations and keep report queries read-only.
- Use a dedicated reconciliation/query plan for correctness checks.
