# Conservative fuzzy correction

Area: backend · Status: planned

## Purpose

Vocabulary-backed correction is partially written but blocked by missing/self imports. The proposed policy protects technical tokens and preserves original queries; no public fuzzy fallback is active.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/retrieval/fuzzy`](../../../backend/src/backend/search/retrieval/fuzzy)
- [`backend/src/backend/schema/search_term.py`](../../../backend/src/backend/schema/search_term.py)

## How-it-works docs

- [`backend/tests/fuzzy_test_case.md`](../../../backend/tests/fuzzy_test_case.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0025](ADR-0025-conservative-fuzzy-suggestions.md) | decision | Suggest bounded spelling corrections without silently rewriting developer queries | proposed |
| [INC-0008](INC-0008-fuzzy-import-contract-broken.md) | incident | Fuzzy correction imports missing and self-referenced symbols | open |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0025. Do not mark them accepted solely because this overview exists.

## Open issues

INC-0008 must be repaired and tested before importing the correction module or enabling fallback.

## Rules for future changes

- Keep fuzzy fallback disabled until imports, candidate SQL and regression tests pass.
- Do not present indexed stems as guaranteed human-friendly suggestions.
- Do not claim fuzzy search is working because its tests or vocabulary table exist.
- Keep the fallback path unconnected until import and PostgreSQL checks pass.
