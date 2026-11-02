# CI and container plan

Area: infra · Status: planned

## Purpose

Records the proposed disposable PostgreSQL and frontend validation gates. No Dockerfile, Compose or CI workflow is present at the inspected baseline; provider and rollout choices are uncommitted.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`frontend/package.json`](../../../frontend/package.json)

## How-it-works docs

The linked source contracts and tests are the current mechanics reference; no separate mechanics guide is claimed.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0039](ADR-0039-reproducible-ci-and-containers-plan.md) | decision | Add disposable PostgreSQL verification before automating deployment | proposed |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0039. Do not mark them accepted solely because this overview exists.

## Rules for future changes

- Make readiness checks distinct from liveness checks.
- Do not mark CI/container work complete until files exist and a run is verified.
