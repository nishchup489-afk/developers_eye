# Search vectors

Area: indexer · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/indexer/vector.py`
- `backend/src/backend/models/search_index.py`

## How-it-works docs
- `crawler/src/indexer/docs/vector.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Two tsvectors: `english` for prose, `simple` for code tokens
- [ ] Postgres full-text search instead of a separate search engine

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
