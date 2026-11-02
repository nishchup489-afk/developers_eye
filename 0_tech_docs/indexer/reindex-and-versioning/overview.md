# Reindex and index format versioning

Area: indexer · Status: active

## Purpose

Versioned index hashes determine freshness beyond raw content changes. Explicit reindex marks reindex:pending rather than deleting searchable rows; resulting freshness is applied by the normal writer.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/indexer/reindex.py`](../../../crawler/src/indexer/reindex.py)
- [`crawler/src/indexer/builder.py`](../../../crawler/src/indexer/builder.py)
- [`crawler/src/indexer/config.py`](../../../crawler/src/indexer/config.py)

## How-it-works docs

- [`crawler/src/indexer/operations.md`](../../../crawler/src/indexer/operations.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0009](ADR-0009-versioned-index-hash-and-pending-marker.md) | decision | Reindexing is driven by a version prefix in indexed_hash and a reindex:pending marker, never by deleting rows | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Bump `INDEXER_INDEX_VERSION` on the worker and the backend together with any change that alters vector output (ADR-0009).
- Add every new indexed field to the `calculate_index_hash` payload (ADR-0009).
- Never force a rebuild by deleting `search_index` rows (ADR-0009).
