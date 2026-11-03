---
id: ADR-0040
title: Bounded Vocabulary Updates and Reduced Advisory-Lock Contention
status: proposed
date: 2026-11-02
area: indexer
feature: vocabulary
code:
  - crawler/src/indexer/vocabulary.py:synchronize_vocabulary
  - crawler/src/indexer/vocabulary.py:lock_vocabulary
  - crawler/src/indexer/writer.py:persist_search_vectors
  - crawler/src/indexer/writer.py:remove_search_index
  - crawler/src/crawler/worker/jobs/utility.py:_finalize
  - crawler/src/indexer/vocabulary_rebuild.py:rebuild_vocabulary
  - crawler/tests/indexer/test_vocabulary.py
supersedes:
superseded_by:
related:
  - INC-0032
---

# ADR-0040: Bounded Vocabulary Updates and Reduced Advisory-Lock Contention

## TL;DR

Developer's Eye will maintain vocabulary document frequencies using bounded, batched updates instead of repeatedly upserting the complete term set inside a per-term loop.

We will retain the shared PostgreSQL advisory lock for vocabulary consistency while restricting its use to operations that actually require vocabulary coordination. This addresses the quadratic write-amplification defect and reduces crawler stalls caused by database lock contention.

## Context

On November 2, 2026, Developer's Eye experienced severe crawler throughput degradation.

The crawler scheduler remained functional, but workers repeatedly exceeded the configured 240-second job deadline.

The diagnostic snapshot showed:

- 56,391 queued URLs eligible for crawling.
- Three online crawler workers.
- 106 recorded job timeouts during the seven-day reporting window.
- Successful HTTP fetch and parsing operations followed by failed job finalization.
- Six PostgreSQL sessions waiting on an advisory lock.
- A blocking PostgreSQL backend executing a bulk `INSERT INTO search_terms`.

### Existing architecture

The indexer executes the following sequence:

1. Select a document requiring indexing.
2. Build its searchable TSVECTOR representations.
3. Acquire the shared vocabulary advisory lock.
4. Persist the search index.
5. Execute `synchronize_vocabulary()`.
6. Commit the transaction and release the advisory lock.

Vocabulary synchronization is a function invoked by the indexer, not a separate background worker.

The crawler also used the same advisory lock during finalization, including normal document persistence.

### Identified defect

The original synchronization code performed a bulk insertion of all added terms from inside a loop iterating over those same terms.

For N newly introduced terms:

- Outer loop: N iterations.
- Inner bulk insertion: N terms per iteration.
- Total term-level operations: O(N²).

For example, 1,000 newly added terms could cause approximately 1,000,000 row-level upsert operations instead of 1,000.

This also created a correctness defect because repeated `ON CONFLICT DO UPDATE` operations could increment the same term's `document_frequency` multiple times for one document.

### Constraints

- Preserve PostgreSQL 16 as the existing persistence layer.
- Retain transactional consistency between `search_index` and `search_terms`.
- Avoid introducing another worker, queue, or external service.
- Support concurrent crawler and indexer processes.
- Prevent lost increments, negative frequencies, and lock-order inversions.
- Keep implementation complexity appropriate for the current MVP.

## Decision

### 1. Replace repeated upserts with bounded batch updates

Compute vocabulary differences once:

- `added = new_terms - old_terms`
- `removed = old_terms - new_terms`

Normalize and deduplicate terms before calculating changes.

Use sorted term order and a batch size of **500 terms**.

For additions, perform a batched PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`, incrementing each term's document frequency exactly once.

For removals, use batched `UPDATE ... RETURNING` statements. Delete rows whose document frequency reaches zero.

Missing or invalid frequency rows must raise an exception and roll back the transaction rather than silently corrupting counts.

The intended term-update work is O(N) for N changed terms, excluding sorting, statement planning, and database indexing costs.

### 2. Preserve transactional vocabulary consistency

Keep the existing transaction-scoped PostgreSQL advisory lock:

`pg_advisory_xact_lock(7331090042)`

The indexer must acquire this lock before mutating the search index and its vocabulary statistics.

Vocabulary increments, decrements, and index changes must remain in the same database transaction.

The lock is released automatically when the transaction commits or rolls back.

### 3. Reduce unnecessary crawler lock acquisition

Ordinary crawler document persistence does not directly modify vocabulary document frequencies.

The crawler therefore should not acquire the global vocabulary mutex for every successful crawl.

Acquire the vocabulary lock when finalization can remove indexed documents or change vocabulary statistics, including applicable:

- HTTP 404/410 handling.
- `noindex` document removal.

These operations must continue to be transactionally coordinated with the indexer.

### 4. Standardize lock acquisition order

Where both locks are required, acquire the global vocabulary advisory lock before document-row locks.

Apply this order consistently to indexing, index removal, and crawler index-deletion paths.

### 5. Repair historical vocabulary frequencies

Because the original implementation may have incremented frequencies repeatedly, fixing the code does not automatically repair committed historical values.

Use the existing `indexer.vocabulary_rebuild` command to recalculate document frequencies from the indexed TSVECTOR lexemes.

The rebuild must run with crawler and indexer writers stopped.

This maintenance operation is **planned until verified complete**.

### 6. Keep vocabulary synchronization inside the indexer

Do not introduce a separate `--forever` vocabulary worker.

Normal indexer execution continues to invoke `synchronize_vocabulary()` within its write transaction.

`vocabulary_rebuild` remains a one-shot maintenance command.

## Options considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| A. Batched updates with scoped advisory locking | Fixes repeated writes; preserves existing architecture and atomicity | Global vocabulary writes remain serialized | **Chosen** |
| B. Remove the global advisory lock entirely | Potentially higher concurrency | Requires broader concurrency redesign; introduces ordering and consistency risks | Rejected for MVP |
| C. Dedicated vocabulary worker and queue | Separates indexing from frequency maintenance | Additional infrastructure; eventual-consistency and failure-recovery complexity | Rejected |
| D. Keep existing implementation and increase timeouts | Minimal code changes | Does not fix excessive writes, incorrect frequencies, or lock contention | Rejected |

## Why

### Correctness

A term's document frequency represents the number of indexed documents containing that term.

Each newly indexed document must contribute no more than one increment to that term.

Batched updates eliminate the repeated increment defect, while transactional locking preserves synchronization between indexed vectors and vocabulary statistics.

### Performance

The original algorithm repeated the entire added-term collection during each outer iteration.

The chosen implementation updates each changed term once, significantly reducing database writes.

### Reliability

The original shared-lock usage allowed prolonged vocabulary transactions to delay crawler finalization.

Limiting crawler lock acquisition to vocabulary-sensitive operations reduces unnecessary contention and lowers the risk of worker starvation.

### Operational simplicity

The existing PostgreSQL database, indexer worker, and vocabulary rebuild command are sufficient.

No Redis deployment, distributed queue, or additional service is required.

## Consequences

### Gained

- Elimination of quadratic vocabulary upsert amplification.
- Correct per-document frequency increments for new updates.
- Reduced vocabulary synchronization transaction duration.
- Reduced global-lock contention for ordinary crawler persistence.
- Ability to restore historical frequency correctness using the existing rebuild utility.
- Better separation between crawler document persistence and indexer vocabulary maintenance.

### Accepted limitations / technical debt

- The global vocabulary mutex still serializes concurrent vocabulary writers.
- Very large documents may still produce relatively expensive vocabulary transactions.
- Batch size 500 is an initial engineering choice, not a benchmark-optimized value.
- Removing the global mutex requires further concurrency analysis.
- Historical frequency correctness requires a completed rebuild and validation.

### What now depends on this decision

- `search_terms.document_frequency`
- Fuzzy search and vocabulary-based suggestions
- Indexer transaction correctness
- Crawler/indexer concurrency
- Indexed-document removal
- Vocabulary rebuilding and drift repair

## Invariants

1. A document contributes at most one count to each distinct indexed term.
2. Unchanged lexeme sets produce no vocabulary writes.
3. A newly added term contributes exactly `+1` to document frequency.
4. A removed term contributes exactly `-1`.
5. Document frequencies must never become negative.
6. Zero-frequency terms are removed.
7. Missing decrement targets raise an error rather than silently passing.
8. Every search-index mutation and its vocabulary delta commit atomically.
9. Every vocabulary-changing transaction participates in the shared locking protocol.
10. Ordinary crawler document writes must not require the global vocabulary lock.
11. Code paths needing both vocabulary and document-row locks acquire them in a consistent order.
12. The vocabulary rebuild must reproduce frequencies from the actual indexed document set.

## Failure modes

| Failure | Handling |
|---|---|
| Excessive vocabulary insert operations | Bounded batches; process each changed term once |
| Global advisory-lock contention | Minimize transaction work and restrict crawler lock acquisition |
| Incorrect historical DF | Rebuild from indexed TSVECTOR lexemes |
| Missing term during decrement | Raise `RuntimeError`; roll back |
| Worker cancellation or timeout | Transaction rollback releases transaction-scoped locks |
| Inconsistent lock acquisition order | Enforce and test consistent lock ordering |
| Concurrent index modifications | Shared vocabulary mutex and document-row synchronization |

**Related incident:** INC-0032, crawler finalization stalled by PostgreSQL advisory-lock contention.

## Evidence

### Measured

November 2, 2026 crawler snapshot:

- 56,391 eligible queued targets.
- Three online crawler workers.
- 106 recorded timeouts across the reporting window.
- Repeated successful fetch and parse events preceding job deadlines.
- Configured job deadline: 240 seconds.

PostgreSQL diagnostic:

- Six sessions waiting on an advisory lock.
- Blocking backend PID `27344` observed executing a bulk `INSERT INTO search_terms`.
- Waiting-query durations reached approximately 155 seconds.

User-observed recovery:

- Crawler processing resumed following local remediation work.

### Confirmed code defect

The original `synchronize_vocabulary()` implementation repeatedly executed a multirow upsert inside the loop over newly added terms.

This creates quadratic row-level write amplification and potentially inflates document frequencies.

### Assumed / not yet verified

- The precise identity of the blocking transaction has not been conclusively established as normal indexing rather than maintenance work.
- The complete proposed patch has not been verified in GitHub `main`.
- Historical vocabulary repair has not been confirmed.
- Sustained concurrent crawler/indexer performance after the fix has not yet been benchmarked.

### Tests

Required regression coverage:

- Single-term insertion.
- Multiple added terms produce one increment per term.
- Unchanged terms produce no write.
- Removed terms decrement correctly.
- Zero-frequency terms are deleted.
- Missing frequencies cause rollback.
- Concurrent crawler and indexer writers preserve consistency.
- Advisory-lock acquisition follows the documented order.
- Vocabulary rebuild matches independently calculated document frequencies.

The multiple-addition regression test must assert that three new terms do not trigger three repeated bulk upserts.

### Commits

Not verified. Add the implementation commit identifier when the patch is committed.

## Revisit when

Re-evaluate this decision if any of the following occurs:

- Advisory-lock wait p95 exceeds **250 ms** for 15 consecutive minutes under normal workload.
- Crawler finalization p95 exceeds **5 seconds** due primarily to lock waits.
- Any production job again reaches the 240-second deadline because of vocabulary locking.
- Corpus size exceeds **1 million indexed documents**.
- Concurrent indexing requires more than **8 active writer tasks**.
- Vocabulary synchronization becomes a measured throughput bottleneck after the current fixes.

These are proposed engineering thresholds and must be validated against real operating measurements.

## Rules for future changes

- Do not replace the shared vocabulary mutex without a new ADR and concurrency tests.
- Do not place whole-collection database operations inside a per-term loop.
- Do not modify document frequencies without computing set-based deltas.
- Do not increment a term more than once for a single document.
- Do not remove indexes without preserving vocabulary consistency.
- Do not acquire document-row locks before the vocabulary mutex in paths requiring both.
- Do not modify vocabulary batch sizes without performance measurements.
- Before editing, inspect `indexer/vocabulary.py`, `indexer/writer.py`, and crawler finalization.
- Regression tests that must keep passing: vocabulary delta tests, multi-term write-amplification regression, index-removal tests, and concurrent crawler/indexer integration tests.