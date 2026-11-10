---
id: ADR-0051
title: One test runner script orchestrates the native suite runners and reports through rich
status: accepted
date: '2026-11-10'
area: infra
feature: local-dev-and-testing
code:
- scripts/run_all_tests.py
- backend/pyproject.toml
- crawler/pyproject.toml
- frontend/package.json
supersedes: null
superseded_by: null
related:
- ADR-0035
---

# ADR-0051: One test runner script orchestrates the native suite runners and reports through rich

## TL;DR
`python scripts/run_all_tests.py` runs every suite with the runner it already has (pytest per Poetry
project, npm scripts in `frontend/`) and prints one rich diagnostics report. It never moves tests or
merges pytest sessions, because the suites only work from their own folders.

## Context
The app has four kinds of checks: backend pytest (~537 tests), crawler and indexer pytest (~720),
frontend lint, typecheck and Node `.mjs` scripts, plus frontend tests that need a production build.
Each needs a different folder, interpreter and environment (`TEST_DATABASE_URL`, a free port, a `.next`
build). Running all of them meant remembering five commands and reading five output formats, and a
skipped PostgreSQL tier looked the same as a pass. ADR-0035 already asks that a report say which checks
ran, which skipped and which need PostgreSQL.

## Decision
- One script, `scripts/run_all_tests.py`, standard library plus `rich` (already a dev dependency of both
  Poetry projects). If the starting Python has no `rich`, it re-runs itself with `crawler/.venv`,
  `backend/.venv` or the Poetry env.
- Suites: `backend` (`cd backend && pytest`), `crawler` (`cd crawler && pytest tests/crawler`),
  `indexer` (`cd crawler && pytest tests/indexer`), `fe-lint`, `fe-types`, `fe-admin-unit`,
  `fe-search-unit`; with `--with-build` also `fe-build` and the four build-dependent npm scripts.
  Suites run one after another, never in parallel, because backend, crawler and indexer share one test DB.
- pytest results come from `--junitxml` (per test outcome, time, message, short traceback). Node scripts
  are judged by exit code; their `PASS ...` lines are counted as passed checks.
- Each pytest suite uses its project's own interpreter (in-project `.venv`, then `poetry env info`, then the
  current Python; `--python` overrides). `PYTHONPATH` gets both `src/` folders, as the per-package docs say.
- Test settings live in one git-ignored file, the repo-root `.env.local` (template `.env.local.example`).
  `backend.core.local_env.load_local_env` reads it from `backend/tests/conftest.py` and
  `crawler/tests/conftest.py`, so plain `pytest` runs get it too; the runner reads the same file for its
  database checks. Only test keys (`TEST_*`, `*_TEST_*`) are read, and a shell variable wins.
- Environment checks: toolchain versions, git state, free disk, `node_modules`, ports 3181/3182, and for the
  test DB: name contains "test", port reachable, login, server version, `pg_trgm`, table count, connections.
- Report: environment table, suite table, skip reasons, slowest tests, failures grouped by shared cause,
  likely-cause hints, verdict. `--save` writes `tests/reports/run-<time>.html/.txt/.json` (git-ignored);
  `--report FILE` writes .html, .svg, .txt or .json. Exit code 0 only when every suite that ran passed.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Orchestrator script over native runners | Suites unchanged; same commands as the docs; one report | Two output formats to parse | chosen |
| B. One pytest session from the repo root | Single native report | Breaks imports (`backend/` shadows the package), mixes two Poetry envs; frontend left out | rejected: does not work |
| C. Makefile / shell script | Small | No Windows parity, no structured results or diagnostics | rejected: user develops on Windows |
| D. tox / nox | Standard tooling | New dependency and env layer on top of Poetry; frontend still separate | rejected: more moving parts than the problem |

## Why
The suites only run from their own folders (see the tests hub and the dev-environment notes), so the
cheapest reliable whole-app run is to call each one exactly as a developer would and read structured
results back. JUnit XML is pytest's stable machine format; `rich` is already installed.

## Consequences
- Gained: one command, one report; DB-dependent skips are listed with their reason instead of hiding in a pass.
- Accepted limitations: Node scripts stop at their first failing assertion, so a failing script counts as one
  failure. On Windows a timeout kills `npm`'s `cmd.exe` but may leave a `next start` child running.
- What now depends on this decision: new suites must be added to `SUITES` in the script.

## Invariants
- The runner never edits test files or the test DB itself; it only runs suites.
- Suites run sequentially and from their own folder.
- Only test keys (`TEST_*`, `*_TEST_*`) are taken from the repo-root `.env.local`; never `DATABASE_URL`.
- Exit code is non-zero when any suite that ran failed or errored.

## Evidence
- Measured (2026-11-10, Linux sandbox, Postgres 16.15, migrated test DB): backend 536 passed / 1 failed
  (sandbox copy lacked `backend/evaluation/queries.json`), crawler 528 passed, indexer 192 passed in 29.5 s;
  all 9 frontend suites including `next build` passed.
- Assumed: Windows behaviour of `npm.cmd` and rich console output; first run on the user's machine confirms it.

## Revisit when
- A suite needs a different runner (Playwright end-to-end in `tests/end-to-end/`), or
- CI runs the suites and wants per-suite jobs instead of one script.

## Rules for future changes
- Add a new suite to `SUITES` in `scripts/run_all_tests.py` and to `frontend/package.json` or `testpaths`, not one or the other.
- Do not run suites in parallel without a per-suite test database.
- Do not load non-test variables from `.env.local` in the runner or the conftests.
