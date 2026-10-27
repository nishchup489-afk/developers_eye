# Database schema and migrations

Area: backend · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `backend/src/backend/models/`
- `backend/alembic/`

## How-it-works docs
- `backend/docs/db/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Alembic is the source of truth; `schema.sql` is a hand-kept snapshot
- [ ] `code_vector` added as NOT NULL without default (fails on non-empty tables)

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
