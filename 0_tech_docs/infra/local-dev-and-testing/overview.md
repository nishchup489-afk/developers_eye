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
| [INC-0036](INC-0036-redirected-windows-test-runner-encoding.md) | incident | Redirected Windows test runner failed before executing suites | resolved |
| [INC-0039](INC-0039-fresh-clone-test-dependencies.md) | incident | Fresh backend Poetry environment could not collect HTTP tests | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Backend development dependencies include both `httpx` (direct async API
  tests) and `httpx2` (Starlette's current TestClient); `poetry install` must
  provide both without borrowing packages from the crawler environment.
- Use the official Node.js 24 build for frontend validation. Ubuntu's packaged
  Node 22 in the clean Linux run omitted native TypeScript support.
- `test_legacy_contracts.py` collects the three rollback-only scheduler scripts
  in pytest/CI and replaces their application session factory with a validated
  `TEST_DATABASE_URL` factory before running them.
- Keep redirected runner output UTF-8 compatible; see INC-0036.
- The orchestrated production build defaults to `.next-test-runner` so active
  development caches are preserved; explicit `NEXT_BUILD_DIR` takes precedence.
  The fresh-stack script uses that same setting and parses database URLs rather
  than splitting strings, preserving socket paths and encoded credentials.

- Report exactly which checks ran, which skipped and which need PostgreSQL.
- Add a new suite to `SUITES` in `scripts/run_all_tests.py` as well as to its own runner (ADR-0051).
- Do not run the suites in parallel without a per-suite test database (ADR-0051).
- Keep the backend-to-crawler dependency direction unchanged.
