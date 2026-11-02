---
id: ADR-0035
title: Keep configuration explicit and distinguish test tiers from deployment evidence
status: accepted
date: '2026-11-02'
area: infra
feature: local-dev-and-testing
code:
- backend/src/backend/core/config.py
- backend/src/backend/db/session.py
- crawler/src/indexer/config.py
- backend/src/backend/search/config.py
- backend/pyproject.toml
- crawler/pyproject.toml
- frontend/package.json
supersedes: null
superseded_by: null
related:
- ADR-0012
- ADR-0022
- INC-0006
- ADR-0039
---

# ADR-0035: Keep configuration explicit and distinguish test tiers from deployment evidence

## TL;DR

Use package-owned configuration with validated limits and separate offline, PostgreSQL and live-network checks. A skipped integration test or authored test file is not evidence that persistence works.

## Context

The codebase spans Python packages, PostgreSQL-specific operations and Next.js. Earlier handoff/test claims mixed local results, written tests and unverified production behavior.

## Decision

Backend settings load the backend environment; indexer/SearchConfig have explicit environment loading paths and constructing defaults does not read all runtime variables automatically. Keep index versions and linguistic configurations aligned between workers, reports and retrieval. Python packages currently declare >=3.14; frontend scripts define their Node test commands. Real PostgreSQL is required for TSVECTOR, GIN, pg_trgm, SKIP LOCKED and advisory locks. Keep live-network tests deliberate and database fixtures disposable. Example environment files contain configuration names, not real credentials.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Validated config and distinct test tiers | Failure causes and evidence are visible | More than one test environment | chosen |
| SQLite/mocks as proof of PostgreSQL behavior | Fast and portable | Cannot prove backend-specific semantics | rejected |
| Use production data for convenient tests | Realistic data | Uncontrolled state changes and reproducibility | rejected |

## Why

Validation has to match the feature: pure functions can be checked offline, while lock behavior and search SQL need the actual database.

## Consequences

- Gained: Honest validation reports and reproducible local boundaries.
- Accepted limitations / tech debt: Dependencies and environment examples alone do not prove a deployment; current CI/containers are still planned.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Schema/index version changes have a migration/rebuild rollout plan.
- Missing TEST_DATABASE_URL is reported as skipped, not passed.
- Credentials are never copied into docs, fixtures or reports.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/src/backend/core/config.py`](../../../backend/src/backend/core/config.py)
- [`backend/src/backend/db/session.py`](../../../backend/src/backend/db/session.py)
- [`crawler/src/indexer/config.py`](../../../crawler/src/indexer/config.py)
- [`backend/src/backend/search/config.py`](../../../backend/src/backend/search/config.py)
- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`frontend/package.json`](../../../frontend/package.json)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/tests/test_package_boundary.py`](../../../backend/tests/test_package_boundary.py)
- [`crawler/src/indexer/tests`](../../../crawler/src/indexer/tests)
- [`frontend/tests`](../../../frontend/tests)

## Revisit when

- A dependency/runtime version changes or a new environment variable affects public behavior.

## Rules for future changes

- Report exactly which checks ran, which skipped and which need PostgreSQL.
- Keep the backend-to-crawler dependency direction unchanged.
