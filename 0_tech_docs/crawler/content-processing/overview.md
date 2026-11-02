# Content normalization, classification and fingerprints

Area: crawler · Status: active

## Purpose

Normalizes extracted content, classifies by rules and fingerprints searchable payload. Content_hash is separate from the versioned index hash; changes in indexed metadata still matter.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/processing`](../../../crawler/src/crawler/processing)

## How-it-works docs

- [`crawler/src/crawler/processing/docs/content_processing.md`](../../../crawler/src/crawler/processing/docs/content_processing.md)
- [`crawler/src/crawler/processing/docs/fingerprint.md`](../../../crawler/src/crawler/processing/docs/fingerprint.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0019](ADR-0019-normalize-classify-fingerprint.md) | decision | Normalize before deterministic classification and content fingerprinting | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Version changes to fingerprint semantics.
- Keep content and index hashes conceptually separate.
