# Conservative fuzzy correction

Area: backend · Status: active

## Purpose

Vocabulary-backed spelling suggestions for the results page's "Did you mean" (ADR-0045). `GET /search/suggest` returns a correction that only a user click applies; `/search` never rewrites a query. Stems from the vocabulary are mapped back to real words before they are shown.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/retrieval/fuzzy`](../../../backend/src/backend/search/retrieval/fuzzy)
- [`backend/src/backend/schema/search_term.py`](../../../backend/src/backend/schema/search_term.py)

## How-it-works docs

- [`backend/tests/test_case.md`](../../../backend/tests/test_case.md) (Fuzzy suggestions section)
- [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md) (`/api/search/suggest`, `/search/suggest`)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0045](ADR-0045-did-you-mean-with-surface-word-suggestions.md) | decision | Offer "Did you mean" on few results, with stems mapped back to real words | accepted |
| [ADR-0025](ADR-0025-conservative-fuzzy-suggestions.md) | decision | Suggest bounded spelling corrections without silently rewriting developer queries | superseded |
| [INC-0008](INC-0008-fuzzy-import-contract-broken.md) | incident | Fuzzy correction imports missing and self-referenced symbols | resolved |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0025. Do not mark them accepted solely because this overview exists.

## Open issues

A bare stem can still be suggested when the typo is closer to it than to any rebuilt word; the trigram threshold of 0.2 has not been measured at 2M documents (see ADR-0045 "Revisit when").

## Rules for future changes

- Do not make `/search` apply suggestions automatically without a new ADR.
- Do not return candidate stems without the `english_stem` round-trip check.
- Keep `maxSuggestQueryLength` in `frontend/lib/search.ts` equal to `MAX_QUERY_CHARS` in `correction.py`.
- Change the trigram threshold only transaction-locally, and re-run the integration tests.
- Regression tests: `backend/tests/unit/test_fuzzy_suggestions.py`, `backend/tests/integration/test_fuzzy_suggestions.py`, `backend/tests/api/test_search.py`, `npm run test:search:unit`, `npm run test:integration`.
