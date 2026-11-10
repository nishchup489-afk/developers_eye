---
id: INC-0039
title: Fresh backend Poetry environment could not collect HTTP tests
status: resolved
date: 2026-11-09
severity: medium
area: infra
feature: local-dev-and-testing
code: [backend/pyproject.toml, backend/poetry.lock, .github/workflows/ci.yml]
fix_commits: [dc42b28]
related: [ADR-0051]
---

# INC-0039: Fresh-clone HTTP test dependencies

## Reproduction and cause

Clone `fix/checklist` into a clean Linux directory, run `poetry -C backend
install`, and run backend pytest. Seven modules fail collection: direct async
tests import `httpx`, while Starlette TestClient requires `httpx2` or its
deprecated HTTPX fallback. Neither client was declared in backend dev dependencies.
The existing Windows environment happened to contain HTTPX. A combined crawler
environment also masked the missing backend declaration.

## Resolution

Declare both test clients in the backend dev group and lock their dependencies.
Include HTTPX2 explicitly in CI's combined pip environment, which resolves
dependencies separately from Poetry. Keep the crawler's transport on its
existing HTTPX API. Fresh Poetry installation and all 547 backend tests now pass
on Linux without borrowing the crawler environment.

The first Linux run also used Ubuntu's Node 22 package compiled without native
TypeScript support. Its TS-importing frontend tests failed with
`ERR_NO_TYPESCRIPT`. Install the checksum-verified official Node 24 distribution
used by CI; document that requirement in the frontend README. No application
TypeScript behavior needed changing.

## Verification

The fresh Linux checkout passes all twelve orchestrated suites, 1,328 tests and
checks, with no skips. Three formerly standalone rollback-only scheduler
contracts are now collected by pytest, using a validated disposable database
factory instead of the imported application factory. Release/browser/deployment
validation remains a separate scope.
