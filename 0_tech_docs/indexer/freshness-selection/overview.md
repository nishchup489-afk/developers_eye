# Freshness selection (no queue)

Area: indexer · Status: active

## Purpose
Finds indexing work without a queue: read-only queries for available documents whose index row is missing, stale or from another index version, and for index rows whose document is gone or unavailable. Candidates are hints; the writer revalidates. It does not build vectors or write rows.

## Code
- `crawler/src/indexer/selector.py`

## How-it-works docs
- `crawler/src/indexer/docs/selector.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0008](ADR-0008-indexer-work-derived-from-freshness-no-queue.md) | decision | Indexer work is derived from freshness, with no queue or lease table | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] No queue or lease table: work derived from `document.updated_at` vs `search_index` (ADR-0008)
- [ ] No failure backoff yet (a failing document is reselected every poll)

## Rules for future changes
- Every path that changes indexed `document` fields must set `updated_at` (ADR-0008).
- The selector never writes or locks (ADR-0008).
- A failing document is reselected every poll until failure backoff exists (ADR-0008, open).
