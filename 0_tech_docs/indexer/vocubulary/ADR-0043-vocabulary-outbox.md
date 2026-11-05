---
id: ADR-0043
title: Update vocabulary counts through a transactional outbox, not a global lock
status: accepted
date: '2026-11-05'
area: indexer
feature: vocubulary
code:
- crawler/src/indexer/vocabulary.py
- crawler/src/indexer/writer.py
- crawler/src/indexer/worker/runner.py
- backend/alembic/versions/b7d2f4a9c1e3_vocabulary_change_outbox.py
supersedes: ADR-0036
superseded_by: null
related:
- ADR-0002
- EXP-0006
- EXP-0008
- INC-0007
---

# ADR-0043: Update vocabulary counts through a transactional outbox, not a global lock

## TL;DR

An index write now appends its added and removed terms to `vocabulary_change` in its own transaction. One drainer at a time folds those rows into `search_terms`. Writers no longer wait for each other, and counts stay exact.

## Context

ADR-0036 made every index write hold one advisory lock. That fixed the counts, and EXP-0006 was planned to measure the cost. The measurement: about 60 documents/s at any concurrency from 1 to 8. A lock that flat means extra workers do nothing. A full reindex of 2M documents would take almost 4 days.

## Decision

- Writers add one `vocabulary_change(added, removed)` row, committed with the index row. A rollback removes it too.
- `drain_vocabulary_changes` takes a try-lock, reads up to 2,000 rows, sums deltas per term and applies them, all in one transaction. A crash cannot lose a change or apply one twice.
- Any indexer process can drain. If another one holds the lock, it returns at once.
- A term reaching 0 is deleted. A delta for a missing term is ignored, because this table is derived data and `vocabulary_rebuild` repairs it.
- Indexer processes split work with `id % shard_count == shard_index`, so they never duplicate a document.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Outbox with one drainer | Exact counts, no writer contention, common terms written once per batch | Counts trail the index by one drain | chosen |
| Finer locks per term | Keeps counts synchronous | Deadlock risk, and common words still serialize | rejected |
| Periodic full recount with ts_stat | Very simple | Minutes of scanning at 2M | rejected |
| Remove counts entirely | Nothing to maintain | Spelling suggestions need frequencies | rejected |

## Why

Spelling suggestions do not need counts that are correct to the millisecond. They need counts that never drift. An outbox gives that, and summing per term removes the hottest writes.

## Consequences

- Gained: 60 to 170 documents/s in one process, 581 with 4 processes, with 0 wrong counts in an exact recount (EXP-0008).
- Accepted limitations / tech debt: suggestions lag the index by one drain cycle, about one batch.
- The crawler no longer takes any lock on 404 or noindex, but it still deletes those index rows itself. Moving that to the indexer is open.

## Invariants

- The change row and the index write commit in one transaction.
- Only the drainer or a rebuild writes `search_terms`.
- `vocabulary_rebuild` clears `vocabulary_change` in the same transaction as its recount.

## Evidence

- [`crawler/tests/indexer/test_vocabulary_outbox.py`](../../../crawler/tests/indexer/test_vocabulary_outbox.py)
- [`crawler/tests/benchmarks/bench_indexer.py`](../../../crawler/tests/benchmarks/bench_indexer.py)

## Revisit when

- Queue length in `vocabulary_change` grows without falling, which means the drain cannot keep up.
