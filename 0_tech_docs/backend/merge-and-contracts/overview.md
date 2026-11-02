# Candidate merge and data contracts

Area: backend · Status: active

## Purpose

Merges immutable typed candidates by document ID, preserving independent maxima per channel. Final ranking and public metadata enrichment are separate stages and are not wired through these types yet.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/merge.py`](../../../backend/src/backend/search/merge.py)
- [`backend/src/backend/search/types.py`](../../../backend/src/backend/search/types.py)

## How-it-works docs

The linked source contracts and tests are the current mechanics reference; no separate mechanics guide is claimed.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0026](ADR-0026-merge-channel-scores-by-document.md) | decision | Merge candidates by document ID while retaining independent channel evidence | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Add explicit retriever-to-RetrievalHit adapters.
- Preserve order independence, input immutability and duplicate-hit idempotence in tests.
