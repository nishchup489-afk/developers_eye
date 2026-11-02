---
id: ADR-0037
title: Treat coverage and vocabulary reports as operational observations
status: accepted
date: '2026-11-02'
area: indexer
feature: coverage-reporting
code:
- backend/src/backend/admin_services/indexer_reporting.py
- backend/src/backend/admin_services/vocabulary_reporting.py
- crawler/src/indexer/reporting.py
- frontend/components/admin/indexer-control-center.tsx
- frontend/components/admin/vocabulary-report.tsx
supersedes: null
superseded_by: null
related:
- ADR-0030
- ADR-0036
---

# ADR-0037: Treat coverage and vocabulary reports as operational observations

## TL;DR

Report coverage, freshness and vocabulary health using read-only database queries. These observations are not a transactional proof of correctness or historical throughput measurements.

## Context

Operators need to see missing/stale/old-version index work and vocabulary state while workers keep changing the database.

## Decision

Coverage compares available documents with index presence, indexed_at and active version; source-scoped reporting is supported. Aggregate totals and per-source rows are separate READ COMMITTED statements, so concurrent writes can make them differ. Vocabulary reporting reads current counts/sample terms; it does not independently recount source vectors. The CLI and admin UI surface these backend reports rather than implementing another writer.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Lightweight operational reports | Useful while workers run | Different statements can see different snapshots | chosen |
| Require a global pause for every report | Consistent frozen numbers | Interrupts normal operations | rejected |
| Treat search_terms totals as verified truth | Cheap apparent health check | Hides vocabulary drift | rejected |

## Why

A live dashboard should describe what it observed and when. Correctness reconciliation and historical analytics need additional data and stronger snapshot semantics.

## Consequences

- Gained: Coverage visibility without changing worker state.
- Accepted limitations / tech debt: Counts can drift during a report; a healthy-looking report does not prove ranking quality, no drift, or a QPS claim.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Reports do not mutate/rebuild the index.
- Index-version settings match the worker when interpreting stale work.
- Observed counts are not reused as per-channel ranking corpus statistics without a defined contract.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/src/backend/admin_services/indexer_reporting.py`](../../../backend/src/backend/admin_services/indexer_reporting.py)
- [`backend/src/backend/admin_services/vocabulary_reporting.py`](../../../backend/src/backend/admin_services/vocabulary_reporting.py)
- [`crawler/src/indexer/reporting.py`](../../../crawler/src/indexer/reporting.py)
- [`frontend/components/admin/indexer-control-center.tsx`](../../../frontend/components/admin/indexer-control-center.tsx)
- [`frontend/components/admin/vocabulary-report.tsx`](../../../frontend/components/admin/vocabulary-report.tsx)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/src/indexer/tests`](../../../crawler/src/indexer/tests)
- [`frontend/tests/indexer-report-unit.mjs`](../../../frontend/tests/indexer-report-unit.mjs)

## Revisit when

- Cross-table report consistency is needed for an automated action.
- Report query cost competes with search traffic.

## Rules for future changes

- Label snapshot limitations and keep report queries read-only.
- Use a dedicated reconciliation/query plan for correctness checks.
