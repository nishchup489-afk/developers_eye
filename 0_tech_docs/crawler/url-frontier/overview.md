# URL frontier and crawl scope

Area: crawler · Status: active

## Purpose

Owns conservative URL identity, deduplicated enqueueing and source depth/path/page budgets. This is insertion policy; scheduler ordering and destination network approval are separate responsibilities.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/frontier`](../../../crawler/src/crawler/frontier)
- [`backend/src/backend/models/crawler_frontier.py`](../../../backend/src/backend/models/crawler_frontier.py)

## How-it-works docs

- [`crawler/src/crawler/frontier/tests/test_case.md`](../../../crawler/src/crawler/frontier/tests/test_case.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0015](ADR-0015-url-identity-and-bounded-frontier.md) | decision | Normalize URL identity conservatively and enforce crawl scope at insertion | accepted |
| [INC-0002](../worker-runtime/INC-0002-deadlocks-in-crawl-finalization.md) | incident | Multi-worker stress test deadlocked crawl finalization and left attempts unfinished | resolved |
| [INC-0003](INC-0003-crawl-scope-limits-never-enforced.md) | incident | Source max_depth was configured but never read, so the frontier grew without limit | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Create targets only through `enqueue_targets()` so depth and budget rules apply (INC-0003).
- Keep the per-source advisory lock around count-then-insert, taken in ascending `source_id` order (INC-0003).
- Deduplicate and sort by `(source_id, normalized_url)` before inserting (INC-0002).
- Any new `source.config` key needs code that reads it and a test that fails if it is ignored (INC-0003).
- Do not strip query parameters globally.
- Keep all enqueue paths behind scope checks and deterministic lock ordering.
