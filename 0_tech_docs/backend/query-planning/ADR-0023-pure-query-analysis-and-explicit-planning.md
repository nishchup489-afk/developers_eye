---
id: ADR-0023
title: Keep query normalization and retrieval planning pure and explicit
status: accepted
date: '2026-11-02'
area: backend
feature: query-planning
code:
- backend/src/backend/search/query_analyzer/analyzer.py
- backend/src/backend/search/query_selector/planner.py
- backend/src/backend/search/config.py
- backend/src/backend/api/search.py
supersedes: null
superseded_by: null
related:
- ADR-0024
- ADR-0028
---

# ADR-0023: Keep query normalization and retrieval planning pure and explicit

## TL;DR

The new analyzer validates and normalizes input without I/O; the planner selects explicit text/code/all targets without searching. These modules exist but are not yet used by the public route.

## Context

Developer queries contain meaningful case, punctuation, identifiers and phrases. Rewriting them aggressively before PostgreSQL analysis can destroy intent, while unbounded Unicode processing has avoidable cost.

## Decision

Check raw length first (default 1,024), reject invalid Unicode/control formatting, normalize NFC, collapse whitespace outside double quotes, preserve phrase spacing, then check normalized length (default 256). Keep identifiers/case/punctuation. The planner trims input and maps all/text/code to retrieval targets; it does not infer code intent or perform typo correction. The current route separately accepts 300 characters and collapses whitespace, so routing through the new analyzer is an integration change, not already delivered behavior.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Pure analyzer plus explicit mode | Deterministic, easy to test | Caller must actually wire it in | chosen |
| Python stemming and punctuation stripping | One apparent normalization layer | Can disagree with PostgreSQL and damage identifiers | rejected |
| Infer code mode from punctuation alone | Less UI input | Ambiguous queries get silently routed | deferred until evaluated |

## Why

Validation, linguistic analysis and routing are separate responsibilities. PostgreSQL should own the lexemes used by its index.

## Consequences

- Gained: Structured errors exclude raw query text and module behavior is independently testable.
- Accepted limitations / tech debt: Current route and component limits differ. Default SearchConfig construction does not automatically load SEARCH_* environment variables.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Analyzer and planner perform no SQL/network work.
- SQL callers still bind query values.
- Explicit mode is validated; empty input is rejected.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Analyzer milestone: [884d07c](https://github.com/nishchup489-afk/developers_eye/commit/884d07cd85a65ea3c9c81f3dfe052739c7d92020).

- [`backend/src/backend/search/query_analyzer/analyzer.py`](../../../backend/src/backend/search/query_analyzer/analyzer.py)
- [`backend/src/backend/search/query_selector/planner.py`](../../../backend/src/backend/search/query_selector/planner.py)
- [`backend/src/backend/search/config.py`](../../../backend/src/backend/search/config.py)
- [`backend/src/backend/api/search.py`](../../../backend/src/backend/api/search.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/tests/integration/test_analyzer.py`](../../../backend/tests/integration/test_analyzer.py)

## Revisit when

- Before connecting the modular pipeline to GET /search.
- Before introducing automatic mode detection or changing query length limits.

## Rules for future changes

- Reconcile the frontend, route and analyzer contracts in one integration change.
- Do not call the query analyzer a PostgreSQL tokenizer.
