# Seeds and discovery

Area: crawler · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/crawler/seed/`

## How-it-works docs
- `crawler/src/crawler/seed/guide.md`
- `crawler/src/crawler/seed/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Source registry kept as JSON plus CSV/XLSX, upserted by `seed.py`
- [ ] Bootstrap discovery through sitemaps, feeds and API endpoints
- [ ] `source.kind` limited to `website`, `rss`, `api`

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
