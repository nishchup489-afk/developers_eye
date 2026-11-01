# Reindex and index versioning

Area: indexer · Status: active

## Purpose
Lets an operator rebuild search vectors without taking documents out of search: a version prefix inside `indexed_hash` for rebuilding everything, and a `reindex:pending` marker for rebuilding chosen documents. The normal indexer worker does the rebuilding; this feature only marks rows.

## Code
- `crawler/src/indexer/reindex.py`
- `crawler/src/indexer/config.py`

## How-it-works docs
- `crawler/src/indexer/operations.md`
- `crawler/src/indexer/docs/config.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0009](ADR-0009-versioned-index-hash-and-pending-marker.md) | decision | Version prefix in indexed_hash and a reindex:pending marker | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] Versioned `indexed_hash` (`v<version>:<sha256>`) and `INDEXER_INDEX_VERSION` bump to rebuild (ADR-0009)
- [x] `reindex:pending` marker instead of deleting rows (ADR-0009)

## Rules for future changes
- Bump `INDEXER_INDEX_VERSION` on the worker and the backend together with any change that alters vector output (ADR-0009).
- Add every new indexed field to the `calculate_index_hash` payload (ADR-0009).
- Never force a rebuild by deleting `search_index` rows (ADR-0009).
