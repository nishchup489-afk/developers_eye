# Weighted PostgreSQL text and code vectors

Area: indexer · Status: active

## Purpose

Builds parameterized to_tsvector/setweight expressions for english prose and simple code fields. GIN supplies an inverted access structure; no separate custom inverted-index service is implemented. simple does not preserve every punctuation-sensitive symbol.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/indexer/vector.py`](../../../crawler/src/indexer/vector.py)
- [`backend/src/backend/models/search_index.py`](../../../backend/src/backend/models/search_index.py)

## How-it-works docs

- [`crawler/src/indexer/docs/vector.md`](../../../crawler/src/indexer/docs/vector.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0010](ADR-0010-two-weighted-tsvectors-in-postgres.md) | decision | Index each document as two weighted Postgres tsvectors, english for prose and simple for code | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Bump `INDEXER_INDEX_VERSION` with any change to fields, weights, configs or vector construction (ADR-0010, ADR-0009).
- Keep `/search` configs equal to the indexer configs (ADR-0010, ADR-0003).
- Bind document text and config names; never interpolate them into SQL (ADR-0010).
