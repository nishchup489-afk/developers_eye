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

2026-11-09 dependency validation: audit the separately installed Poetry environments,
not just a combined crawler/backend environment. Backend's lock carried
`opentelemetry-api` 1.45.0; update to 1.45.2 for
[GHSA-xcq7-p3pf-p88h](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-xcq7-p3pf-p88h).
Crawler's lock carried `certifi` 2026.7.22; update to 2026.10.23 for
[GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2).
These are dependency audit findings; application-level exploitability was not
established. Keep the existing TLS/public-IP policy and verify clean installs
with `pip-audit` after lock updates.

- The 2026-11-09 tooling refresh resolves the Zod/minimatch audit findings without
  changing pinned Next.js 16.4.5. The scoped typescript-estree → minimatch 11.0.5
  override remains until an upstream compatible release includes the fix.
  `npm ci`, full `npm audit`, lint, and TypeScript checks passed after the refresh.

- Make readiness checks distinct from liveness checks.
- Do not mark CI/container work complete until files exist and a run is verified.
