# Local development and validation tiers

Area: infra · Status: active

## Purpose

Separates pure-function, PostgreSQL, network and frontend checks. Historical test counts and newly written tests are evidence with a date/scope, not a passing current full-system run.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/pyproject.toml`](../../../backend/pyproject.toml)
- [`crawler/pyproject.toml`](../../../crawler/pyproject.toml)
- [`frontend/package.json`](../../../frontend/package.json)
- [`scripts/run_all_tests.py`](../../../scripts/run_all_tests.py)

## How-it-works docs

- [`crawler/tests/README.md`](../../../crawler/tests/README.md)
- [`crawler/tests/test_case.md`](../../../crawler/tests/test_case.md#indexer)
- [`frontend/tests/README.md`](../../../frontend/tests/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0035](ADR-0035-configuration-and-validation-boundaries.md) | decision | Keep configuration explicit and distinguish test tiers from deployment evidence | accepted |
| [ADR-0051](ADR-0051-one-runner-over-native-suite-runners.md) | decision | One test runner script orchestrates the native suite runners and reports through rich | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Keep redirected runner output UTF-8 compatible; see INC-0036.

- Report exactly which checks ran, which skipped and which need PostgreSQL.
- Add a new suite to `SUITES` in `scripts/run_all_tests.py` as well as to its own runner (ADR-0051).
- Do not run the suites in parallel without a per-suite test database (ADR-0051).
- Keep the backend-to-crawler dependency direction unchanged.
