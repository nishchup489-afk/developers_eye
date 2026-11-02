# Seeds and discovery

Area: crawler · Status: active

## Purpose

Registers approved sources and discovers initial/page/sitemap/feed/API targets. A configured source or generic JSON parser does not prove every named platform integration exists.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/seed`](../../../crawler/src/crawler/seed)
- [`crawler/src/crawler/main.py`](../../../crawler/src/crawler/main.py)

## How-it-works docs

- [`crawler/src/crawler/seed/guide.md`](../../../crawler/src/crawler/seed/guide.md)
- [`crawler/src/crawler/seed/docs/sitemap_discovery.md`](../../../crawler/src/crawler/seed/docs/sitemap_discovery.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0014](ADR-0014-registered-sources-and-queued-discovery.md) | decision | Register sources and enqueue discovery through the same frontier | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Route new discovery paths through enqueue_targets.
- Keep registry behavior separate from future source coverage claims.
