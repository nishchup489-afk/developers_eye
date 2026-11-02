# Document snapshots and weighted fields

Area: indexer · Status: active

## Purpose

Builds immutable document snapshots and weighted field groups without doing PostgreSQL linguistic analysis in Python. Text weights: title/tags A, headings/description B, body C. Code weights: tags/title A, code blocks/headings B, canonical URL D.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/indexer/builder.py`](../../../crawler/src/indexer/builder.py)
- [`crawler/src/indexer/analyzer.py`](../../../crawler/src/indexer/analyzer.py)
- [`crawler/src/indexer/schemas.py`](../../../crawler/src/indexer/schemas.py)

## How-it-works docs

- [`crawler/src/indexer/docs/builder.md`](../../../crawler/src/indexer/docs/builder.md)
- [`crawler/src/indexer/docs/ANALYZER.md`](../../../crawler/src/indexer/docs/ANALYZER.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0009](../reindex-and-versioning/ADR-0009-versioned-index-hash-and-pending-marker.md) | decision | Reindexing is driven by a version prefix in indexed_hash and a reindex:pending marker, never by deleting rows | accepted |
| [ADR-0010](../search-vectors/ADR-0010-two-weighted-tsvectors-in-postgres.md) | decision | Index each document as two weighted Postgres tsvectors, english for prose and simple for code | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Field and weight changes bump `INDEXER_INDEX_VERSION` (ADR-0010, ADR-0009).
- Add every new indexed field to the `calculate_index_hash` payload (ADR-0009).
