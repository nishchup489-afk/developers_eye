# HTML and structured resource parsing

Area: crawler · Status: active

## Purpose

Extracts documents and discovery links from HTML, XML sitemaps, RSS/Atom and mapped JSON. Parsing is bounded and separate from persistence; page meta policy aggregates every applicable restriction.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/parser`](../../../crawler/src/crawler/parser)

## How-it-works docs

- [`crawler/src/crawler/parser/docs/parser.md`](../../../crawler/src/crawler/parser/docs/parser.md)
- [`crawler/src/crawler/parser/docs/sitemap.md`](../../../crawler/src/crawler/parser/docs/sitemap.md)
- [`crawler/src/crawler/parser/docs/rss_atom.md`](../../../crawler/src/crawler/parser/docs/rss_atom.md)
- [`crawler/src/crawler/parser/docs/json_api.md`](../../../crawler/src/crawler/parser/docs/json_api.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0018](ADR-0018-bounded-format-adapters.md) | decision | Parse HTML, sitemap, feed and JSON resources into explicit shared contracts | accepted |
| [INC-0012](INC-0012-robots-metadata-union.md) | incident | Later or bot-specific robots metadata restrictions were ignored | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Add malformed and boundary fixtures with each adapter change.
- Preserve code indentation and typed discovery links.
- Do not replace all-tag policy aggregation with first-tag lookup.
- Keep parser and crawler bot identity aligned.
