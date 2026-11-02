# BM25 statistics component

Area: backend · Status: active

## Purpose

Batched statistics and validated types are implemented. Position-derived TF/DL are approximate; corpus refresh/caching and consistent snapshot ownership are not implemented by this module.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/ranking/statistics.py`](../../../backend/src/backend/search/ranking/statistics.py)
- [`backend/src/backend/search/ranking/types.py`](../../../backend/src/backend/search/ranking/types.py)

## How-it-works docs

The linked source contracts and tests are the current mechanics reference; no separate mechanics guide is claimed.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0027](ADR-0027-batch-ranking-statistics-and-external-corpus.md) | decision | Batch query statistics and keep full-corpus aggregation outside the request path | accepted |
| [EXP-0003](EXP-0003-ranking-statistics-round-trip-audit.md) | experiment | Static round-trip audit of batched ranking statistics | done |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Open issues

The loader needs live PostgreSQL checks for lexeme/DF/TF consistency and concurrent updates. Two round trips per channel is not two statements for the entire public search request.

## Rules for future changes

- Require PostgreSQL fixtures for stemming, empty/stripped vectors, long documents and concurrent updates.
- Do not use combined search_terms counts as per-channel BM25 DF.
- Persist exact stats only with transactional update/delete/rebuild semantics.
