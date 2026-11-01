# Backend and crawler package boundary

Area: backend · Status: active

## Purpose
Keeps the dependency between the two Python projects one-way: `crawler` (with `indexer`) depends on `backend`, and `backend` never imports either. Shared models, sessions and report queries live in `backend`.

## Code
- `backend/tests/test_package_boundary.py`

## How-it-works docs
- _none yet_

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0012](ADR-0012-crawler-depends-on-backend-never-reverse.md) | decision | The crawler depends on the backend, never the reverse | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] Crawler depends on the backend package, never the reverse (ADR-0012)

## Rules for future changes
- Never import `crawler` or `indexer` from `backend`; move shared code into `backend` (ADR-0012).
- Keep path dependencies relative (ADR-0012).
- Keep passing: `backend/tests/test_package_boundary.py`.
