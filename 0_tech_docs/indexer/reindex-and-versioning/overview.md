# Reindex and index versioning

Area: indexer · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/indexer/reindex.py`
- `crawler/src/indexer/config.py`

## How-it-works docs
- `crawler/src/indexer/operations.md`
- `crawler/src/indexer/docs/config.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Versioned `indexed_hash` (`v<version>:<sha256>`) and `INDEXER_INDEX_VERSION` bump to rebuild
- [ ] `reindex:pending` marker instead of deleting rows

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
