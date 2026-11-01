# Index writer consistency

Area: indexer · Status: active

## Purpose
Persists one prepared index build atomically: locks the source `document` row, rejects stale builds, upserts or deletes `search_index`, and applies vocabulary deltas in the same transaction. It owns the transaction; `repository.py` never commits.

## Code
- `crawler/src/indexer/writer.py`
- `crawler/src/indexer/repository.py`

## How-it-works docs
- `crawler/src/indexer/docs/writer.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0008](../freshness-selection/ADR-0008-indexer-work-derived-from-freshness-no-queue.md) | decision | Writer revalidation is the correctness half of queue-less selection (owned by freshness-selection) | accepted |
| [ADR-0002](../vocubulary/ADR-0002-vocabulary-as-projection-of-index-lexemes.md) | decision | Vocabulary deltas in the writer's transaction (owned by vocubulary) | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] `SELECT ... FOR UPDATE` on the document and freshness re-check before upsert (ADR-0008)

## Rules for future changes
- Do not upsert `search_index` outside `persist_search_vectors()`; keep the `FOR UPDATE` lock and the `updated_at` check (ADR-0008).
- Take `lock_vocabulary()` before the document lock; delete index rows only through `remove_indexed_documents()` (ADR-0002).
