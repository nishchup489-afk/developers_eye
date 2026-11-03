---
id: ADR-0012
title: The crawler package depends on the backend package, never the reverse
status: accepted
date: 2026-10-20
area: backend
feature: package-boundary
code:
  - crawler/pyproject.toml
  - backend/pyproject.toml
  - backend/tests/test_package_boundary.py
  - backend/src/backend/services/
  - crawler/src/crawler/worker/reporting.py
supersedes:
superseded_by:
related: []
---

# ADR-0012: The crawler depends on the backend, never the reverse

## TL;DR
`backend` (FastAPI, models, migrations, read-only report services) is a standalone Poetry package. `crawler` (which contains both the `crawler` and `indexer` packages) depends on it through a relative path dependency, `backend = {path = "../backend", develop = true}`. The backend never imports `crawler` or `indexer`; a test enforces this by failing on any such import. Code that both sides need (models, sessions, report queries) lives in `backend`.

## Context
Before commit `a99f417` (2026-10-20), each project listed the other as a dependency through an absolute path, `C:/Users/nishc/...`. That had two problems (`0_tech_docs/journal/update-log/10_portable_packages.md`):
- the repository only installed on one machine, in one folder;
- the dependency was circular: the backend imported crawler implementation modules just to build the admin reports, so the API could not start without the whole crawler and its HTTP and parsing dependencies installed.

## Decision
- **Direction.** `crawler` → `backend`. The backend owns the schema (SQLAlchemy models, Alembic), the session factory and settings; the crawler and indexer import them.
- **Path dependency.** `crawler/pyproject.toml` has `backend = {path = "../backend", develop = true}`. The checkout can live anywhere.
- **Reports live in the backend.** `services/crawler_reporting.py`, `crawler_monitoring.py`, `indexer_reporting.py` and `vocabulary_reporting.py` query the database directly with the backend's own models. The old crawler commands (`python -m crawler.worker.reporting`, `python -m indexer.reporting`) remain as thin wrappers.
- **Enforcement.** `backend/tests/test_package_boundary.py` starts a fresh interpreter with an import hook that raises if any module named `crawler.*` or `indexer.*` is imported, then imports `backend.main` and checks the admin routes exist.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. `crawler` → `backend` via relative path; reports in the backend | API installs and runs alone; one owner for the schema; works in any folder | Report queries do not reuse crawler code; the backend has to know table semantics the crawler defines | chosen |
| B. Circular absolute-path dependencies (the old state) | Reports could call crawler functions directly | Not installable elsewhere; API pulls in the crawler | rejected: the bug |
| C. A third shared package (`common`: models, session) used by both | Cleanest layering | One more package to version and install | rejected: not worth it at this size |
| D. One monorepo package | No path dependencies | API and workers ship together and share every dependency | rejected |

> **Question for nish:** the indexer lives inside the `crawler` Poetry project. Was that deliberate (share the backend dependency and the venv) or just where it started? If you ever want to run the indexer without the crawler's HTTP stack, this is where you would split it.

## Why
- **Portability.** Anyone can clone and `poetry install` without editing paths.
- **Deployability.** The API runs without HTTPX, BeautifulSoup, lxml or the worker code.
- **One schema owner.** Models and migrations in one place avoid two definitions of the same table drifting apart.

## Consequences
- Gained: a portable checkout and an API that can be deployed on its own.
- Accepted limitations:
  - Some logic is duplicated between the two sides. For example `INDEXER_INDEX_VERSION` is read by both, and the coverage report rebuilds the selector's "current" predicate in SQL. These must be kept in step by hand.
  - A crawler change that needs a schema change always touches the backend package first.
- What depends on this: every crawler and indexer import of `backend.models`, `backend.db.session` and `backend.core.config`.

## Invariants
- No module under `backend/src/backend` imports `crawler` or `indexer`.
- `backend/pyproject.toml` has no dependency on the crawler project.
- No absolute filesystem paths in either `pyproject.toml`.

## Evidence
- Tests: `backend/tests/test_package_boundary.py`.
- Commits: `a99f417`.

## Revisit when
- The indexer needs to be deployed separately from the crawler (split it into its own project that depends on `backend`).
- The backend needs logic that only exists in the crawler (move that logic into `backend`, do not import it).

## Rules for future changes
- Never import `crawler` or `indexer` from `backend`; move shared code into `backend` instead.
- Keep path dependencies relative.
- Keep passing: `backend/tests/test_package_boundary.py`.
