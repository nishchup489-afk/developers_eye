# URL frontier and crawl scope

Area: crawler · Status: active

## Purpose
Turns discovered URLs into `crawl_target` rows: URL normalization, priority, crawl scope (depth, path prefixes, per-source page budget) and deduplicated, deterministically ordered inserts. It does not claim or fetch targets.

## Code
- `crawler/src/crawler/frontier/`

## How-it-works docs
- _none yet_

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [INC-0003](INC-0003-crawl-scope-limits-never-enforced.md) | incident | Crawl scope limits were never enforced | resolved |
| [INC-0002](../worker-runtime/INC-0002-deadlocks-in-crawl-finalization.md) | incident | Deadlocks from unordered link inserts (owned by worker-runtime) | resolved |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] URL normalization rules (`urls.py`)
- [ ] Scope by depth, page budget and path prefix (`max_depth` 3, `max_pages` 10000)

## Rules for future changes
- Create targets only through `enqueue_targets()` so depth and budget rules apply (INC-0003).
- Keep the per-source advisory lock around count-then-insert, taken in ascending `source_id` order (INC-0003).
- Deduplicate and sort by `(source_id, normalized_url)` before inserting (INC-0002).
- Any new `source.config` key needs code that reads it and a test that fails if it is ignored (INC-0003).
