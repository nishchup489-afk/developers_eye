# Local development and validation tiers

Area: infra · Status: active

## Purpose

Separates pure-function, PostgreSQL, network and frontend checks. Historical test counts and newly written tests are evidence with a date/scope, not a passing current full-system run.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`frontend/package.json`](../../../frontend/package.json)

## How-it-works docs

- [`crawler/tests/README.md`](../../../crawler/tests/README.md)
- [`crawler/tests/test_case.md`](../../../crawler/tests/test_case.md#indexer)
- [`frontend/tests/README.md`](../../../frontend/tests/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0035](ADR-0035-configuration-and-validation-boundaries.md) | decision | Keep configuration explicit and distinguish test tiers from deployment evidence | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Report exactly which checks ran, which skipped and which need PostgreSQL.
- Keep the backend-to-crawler dependency direction unchanged.
