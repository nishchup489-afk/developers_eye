# CI and deployment containers

Area: infra · Status: active

## Purpose

CI workflows, container definitions and local verification exist. The selected
deployment is a Vercel frontend and authenticated Oracle API, with PG18 on a
mounted block volume. Local tests do not establish cloud deployment readiness.

Deployment boundary reviewed on 2026-11-10. “Active” means implementation and
local validation exist; it does not mean deployed or verified on Oracle.

## Code

- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`frontend/package.json`](../../../frontend/package.json)
- [`deploy/docker-compose.yml`](../../../deploy/docker-compose.yml)
- [`deploy/Caddyfile`](../../../deploy/Caddyfile)
- [`deploy/tests/smoke_stack.py`](../../../deploy/tests/smoke_stack.py)
- [Container readiness workflow](../../../.github/workflows/oracle-readiness.yml)

## How-it-works docs

The [deployment runbook](../../../deploy/README.md) describes first boot,
PG18 seed transfer, edge authentication, backups and the local verification scope.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0039](ADR-0039-reproducible-ci-and-containers-plan.md) | decision | Add disposable PostgreSQL verification before automating deployment | proposed |
| [ADR-0058](ADR-0058-vercel-to-oracle-authenticated-api.md) | decision | Deploy Vercel behind a scoped authenticated API hop to Oracle | accepted |
| [ADR-0059](ADR-0059-small-opt-in-production-crawl.md) | decision | Run a small opt-in production crawl bounded by source caps and a disk guard | accepted |
| [EXP-0018](EXP-0018-local-oracle-container-readiness.md) | experiment | Verify the local Oracle container and edge-auth boundary | done |

## Decisions to record

ADR-0039 is the earlier proposal. ADR-0058 records the concrete deployment
decision. See [the runbook](../../../deploy/README.md) and
[the readiness checklist](../../journal/oracle_deployment_readiness.md) for
repository evidence and unperformed cloud/operator actions.

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
