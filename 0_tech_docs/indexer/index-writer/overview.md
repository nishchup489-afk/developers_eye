# Index writer consistency

Area: indexer · Status: active

## Purpose

Uses writer-owned sessions/transactions, document row locks and revision checks before committing prepared vectors. Index and vocabulary changes are intended to be atomic; INC-0007 identifies two current violations of count/locking expectations.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/indexer/writer.py`](../../../crawler/src/indexer/writer.py)
- [`crawler/src/indexer/repository.py`](../../../crawler/src/indexer/repository.py)
- [`crawler/src/indexer/vocabulary.py`](../../../crawler/src/indexer/vocabulary.py)

## How-it-works docs

- [`crawler/src/indexer/docs/writer.md`](../../../crawler/src/indexer/docs/writer.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0002](../vocubulary/ADR-0002-vocabulary-as-projection-of-index-lexemes.md) | decision | Fuzzy vocabulary is a projection of stored index lexemes, kept in the index writer's transaction | accepted |
| [ADR-0008](../freshness-selection/ADR-0008-indexer-work-derived-from-freshness-no-queue.md) | decision | Indexer finds work by comparing document and index freshness, with no queue or lease table | accepted |
| [ADR-0036](../vocubulary/ADR-0036-vocabulary-maintenance-and-lock-boundary.md) | decision | Keep vocabulary maintenance transactional and rebuild it with a one-shot CLI | accepted |
| [INC-0007](../vocubulary/INC-0007-vocabulary-overcount-and-uncoordinated-removal.md) | incident | Vocabulary bulk additions repeat and one removal path skips the mutex | open |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Do not upsert `search_index` outside `persist_search_vectors()`; keep the `FOR UPDATE` lock and the `updated_at` check (ADR-0008).
- Take `lock_vocabulary()` before the document lock; delete index rows only through `remove_indexed_documents()` (ADR-0002).
- Fix incremental correctness before recounting and resuming writers.
- Do not reintroduce a permanent vocabulary worker without an ADR.
- Measure contention before replacing the mutex.
- Test multi-term additions, not just a one-term delta.
- Acquire the shared mutex before document locks on every index deletion path.
