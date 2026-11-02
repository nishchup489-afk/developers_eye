---
id: ADR-0039
title: Add disposable PostgreSQL verification before automating deployment
status: proposed
date: '2026-11-02'
area: infra
feature: ci-and-containers
code:
- backend/pyproject.toml
- crawler/pyproject.toml
- frontend/package.json
- backend/alembic/versions
- scripts/update_docs_nav.py
supersedes: null
superseded_by: null
related:
- ADR-0022
- ADR-0035
- ADR-0038
---

# ADR-0039: Add disposable PostgreSQL verification before automating deployment

## TL;DR

Plan CI around offline tests, real disposable PostgreSQL integration and frontend contract/build checks. Container and deployment automation are not implemented in the inspected tree.

## Context

Tests exist across packages, but authored tests and local historical results are not a continuously enforced gate. Search and locking depend on PostgreSQL semantics.

## Decision

Planned pipeline: install declared runtimes/dependencies, apply migrations to an empty disposable PostgreSQL database, exercise upgrade fixtures, run pure and PostgreSQL tests, validate public/admin contracts, then lint/type-check/build the frontend and check docs. Live upstream tests stay opt-in. A Compose setup may supply local PostgreSQL and independently restartable API/crawler/indexer processes. No cloud provider, production rollout or autoscaling system is approved by this record.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Disposable integration environment | Repeatable safety and SQL semantics | CI resources and setup required | proposed |
| Only lint and import checks | Fast | Misses schema, transactions and vector behavior | insufficient |
| Run CI against production | No fixture setup | Unsafe and nonrepeatable | rejected |

## Why

Automated deployment should follow evidence that both clean installs and upgrades preserve search/index invariants.

## Consequences

- Gained: A clear validation gate if implemented.
- Accepted limitations / tech debt: No Dockerfile, Compose file or GitHub Actions workflow is present at the baseline; this PR only records the plan.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Tests use disposable state and never real secrets.
- Skipped PostgreSQL checks do not satisfy the persistence gate.
- Deployment rollout includes migration/backfill/rebuild ordering.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`frontend/package.json`](../../../frontend/package.json)
- [`backend/alembic/versions`](../../../backend/alembic/versions)
- [`scripts/update_docs_nav.py`](../../../scripts/update_docs_nav.py)

## Revisit when

- Before the first automated production deployment or shared integration environment.

## Rules for future changes

- Make readiness checks distinct from liveness checks.
- Do not mark CI/container work complete until files exist and a run is verified.
