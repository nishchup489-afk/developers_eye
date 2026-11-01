# ADR: Maintain Developer's Eye Vocabulary Consistency in the Existing Indexer

**Location:** `tech_docs/`  
**Status:** Implemented in PR #4, with known correctness and performance follow-ups  
**Decision implementation:** [PR #4](https://github.com/nishchup489-afk/developers_eye/pull/4), merged as `c0d1690bef734447cd576046e3da2a5b023cbded`  
**Preceded by:** [PR #3](https://github.com/nishchup489-afk/developers_eye/pull/3)

## Decision statement

Keep the typo-tolerant vocabulary as a **transactionally maintained projection of the existing PostgreSQL full-text search index**. Do not add a second background worker to re-fetch documents or re-tokenize text. Add a one-time rebuild for historical rows and drift repair; route known crawler deletion paths through a shared frequency-maintenance helper; coordinate mutations using one PostgreSQL transaction-scoped advisory lock.

## Context / initial failure

Developer's Eye already has:

```text
Crawler → Document → Indexer → search_index(search_vector, code_vector)
```

The online fuzzy retrieval flow needs a term dictionary (`search_terms`) with document frequencies. An earlier plan proposed a separate `retrieval_vocabulary` worker with its own selector, tokenizer, normalizer and write pipeline. That duplicates information already in the indexer.

PR #3 instead added vocabulary maintenance to the existing writer. Codex review identified four incompletenesses: missing table migration, missing backfill for already indexed documents, crawler deletions that bypass term decrements, and test fixtures that did not isolate the vocabulary table.

PR #4 attempted to repair all four. It was merged before automated review completed. Two new P2 findings then appeared: missing advisory lock in the indexer removal path and a missing AsyncMock for that lock in an unchanged-index unit test.

## Decisions and rationale

### 1. Derive terms from stored `TSVECTOR`s, not raw documents

**Chosen:** `tsvector_to_array(search_vector || code_vector)` plus the existing `vocabulary_terms()` filter.

**Why:** The indexer already determines searchable terms under PostgreSQL `english` and `simple` configurations. Reading those terms avoids a second tokenizer that can disagree with actual retrieval behavior. Use unique per-document terms because the schema stores *document frequency*.

**Trade-off:** English text lexemes are stems, not always complete English words. Code tokens and punctuation can be split or normalized. This dictionary is primarily useful for correcting the indexed lexeme space, not necessarily suggesting beautiful natural-language words.

### 2. Keep updates inside the index writer's transaction

**Chosen:** Compare old/new stored lexeme sets and apply ±1 document-frequency deltas before committing the corresponding `search_index` update.

**Why:** If the index changes but vocabulary does not, the two structures drift. Rollback of both together is essential. Updated documents should only change counts for terms added or removed, not terms preserved across versions.

**Trade-off:** The current implementation uses a SQL operation for each changed term. High throughput may require safe batching or alternative synchronization strategies; keep transactional invariants during any refactor.

### 3. Use a forward repair migration rather than rewriting old migrations

**Chosen:** Add Alembic revision `9a71c3fb20d4` after `da03da123834`.

**Why:** Previous vocabulary revisions were empty and some environments may already have marked them applied. Altering historical migration contents alone would not fix those installations. A new revision makes the required schema explicit for both fresh and already-stamped databases.

**Trade-off:** `IF NOT EXISTS` is conservative but cannot certify that an existing `search_terms` table has the correct columns and constraints. `downgrade()` intentionally does not drop the table to avoid destroying preexisting data, which is operationally safe but not a fully reversible schema migration. Also, future Alembic autogeneration should register the `SearchTerm` model in metadata imports.

### 4. Include historical backfill / drift repair

**Chosen:** A synchronous, manually invoked CLI `python -m indexer.vocabulary_rebuild` (implemented using async SQLAlchemy sessions).

**Why:** PR #3 deltas assume each existing document has already contributed its terms. Previously indexed documents have not. Trying to decrement such an absent term fails, and unchanged documents do not get vocabulary writes. Recounting from all stored vectors establishes a correct baseline.

**Alternative considered:** Force a full reindex of every document. Rejected because stored vectors already contain the lexemes needed, and full reindexing is more expensive and changes source/index version processing unnecessarily.

**Trade-off:** Rebuild streams all indexed documents and stores an in-memory dictionary of distinct terms, then atomically deletes/reinserts vocabulary rows (500-term batches). It can be costly for a very large corpus. Writers should be stopped for operational safety, even though participating code paths use an advisory mutex. The rebuild can only count *existing* index rows.

### 5. Handle crawler-driven index removal in the same transaction

**Chosen:** `remove_indexed_documents(session, document_ids)` reuses `synchronize_vocabulary()` when deleting `SearchIndex` rows.

**Why:** Indexer-initiated removal is not the only deletion path. The crawler's HTTP 404/410 path deletes index rows directly; `noindex` deletes documents and cascades their indexes. The indexer never sees those deleted index rows afterward, so a later indexer cleanup cannot repair counts for them.

**Implementation decision:** Modify both crawler branches to call the helper before/with deletion in the existing `_finalize()` transaction. 404/410 marks a document unavailable; `noindex` removes its `Document` row after removing the index.

**Trade-off:** A shared helper is only a convention, not a database-enforced invariant. Any future hard-delete, cascade or manual SQL bypass can reintroduce drift. New deletion routes must use the same approach, or the team must adopt database-level enforcement.

### 6. Introduce a global transaction-level advisory mutex

**Chosen:** Use one `pg_advisory_xact_lock(7331090042)` per vocabulary-changing transaction.

**Why:** A rebuild that reads the entire index must not race with an indexer update that changes vocabulary. A global mutex is straightforward to implement and released automatically on COMMIT/ROLLBACK.

**Alternative:** Fine-grained per-document or per-term locking. Not implemented in PR #4; it requires careful consistent lock order and a different rebuild coordination strategy.

**Trade-off and known deficiency:** The mutex is coarse. The current crawler takes it in every active `_finalize()` transaction, including paths that do not modify vocabulary. This may severely constrain throughput. Crucially, the indexer `remove_search_index()` path **does not acquire it**, so the intended global synchronization invariant is not fully enforced.

### 7. Isolate the PostgreSQL smoke test's new table

**Chosen:** Add a temporary `search_terms` table alongside the test's temporary `document` and `search_index` tables.

**Why:** PostgreSQL resolves the temporary tables on that connection first. The test can exercise actual SQL without modifying the persistent application vocabulary, meeting the smoke-test's original isolation contract.

**Trade-off:** The integration test requires a correctly configured `TEST_DATABASE_URL` and a real PostgreSQL server. An added lock in the code path also requires `AsyncMock` in unit tests that use a minimal `FakeSession`. One such test was missed and must be fixed.

## Architecture consequences

```text
                Crawler / Document
                       │
                       ▼
               Existing indexer
                       │
              search_index UPSERT
                       │
     old index lexemes vs. new index lexemes
                       │
                       ▼
     search_terms: document_frequency deltas
                       │
                same transaction

404/410, noindex, indexer removal
                       │
                       ▼
           shared index removal helper
                       │
                       ▼
         decrement search_terms counts

Manual backfill / drift repair
                       │
       stream existing search_index rows
                       │
                       ▼
         recompute all search_terms counts
```

No additional crawler pipeline, retrieval worker, or raw-text tokenization service was added. The online fuzzy search reader/matcher is outside PR #4's scope.

## Invariants to preserve

1. One indexed document contributes at most one count per eligible lexeme.
2. Every indexed-row UPSERT that changes terms updates the vocabulary in the same transaction.
3. Every ordinary indexed-row deletion decrements its old vocabulary terms in the same transaction.
4. A failed update or missing expected frequency must roll back both changes.
5. Rebuild must count each **currently indexed** document once and be coordinated with online writers.
6. Manual out-of-band SQL deletion is explicitly unsafe unless followed by reconciliation.
7. Every acquisition order must be reviewed for deadlock safety; a global mutex does not eliminate lock-order mistakes elsewhere.

## Known follow-ups (not done in PR #4)

| Priority | Follow-up | Reason |
|---|---|---|
| High | Add `await lock_vocabulary(session)` at start of `remove_search_index()` transaction, **before** acquiring the Document row lock. | Codex found an unprotected deletion race. [Finding](https://github.com/nishchup489-afk/developers_eye/pull/4#discussion_r4434088290). |
| High | Mock `writer.lock_vocabulary` in `test_writer_unchanged_index()` and execute the unit suite. | FakeSession does not implement `.execute()`. [Finding](https://github.com/nishchup489-afk/developers_eye/pull/4#discussion_r4434088292). |
| High | Run an end-to-end PostgreSQL test against a disposable database before treating the feature as verified. | No passing CI or DB test evidence in the reviewed PR. |
| Medium | Narrow crawler lock acquisition to vocabulary-changing paths while preserving a consistent lock order. | Every active crawler finalization currently competes for one global mutex. |
| Medium | Audit all other cascade deletes, maintenance scripts, and direct SearchIndex changes. | They may bypass vocabulary decrements. |
| Medium | Register `SearchTerm` in Alembic model imports and inspect future migration autogeneration. | The current `backend.models` package does not import it in the reviewed commit. |
| Medium | Benchmark per-term UPSERT/UPDATE SQL at realistic document sizes; consider batched deltas. | An individual SQL statement per changed term may become expensive. |
| Future | Consider a spell-correction source that preserves unstemmed developer terms. | PostgreSQL English stems are not a complete user-facing dictionary. |

## Validation / exit criteria

PR #4's code is merged, not independently certified. Treat the behavior as validated only when:

- Alembic upgrade succeeds in a fresh test DB and a previously stamped test DB.
- Rebuild runs successfully, and a second rebuild produces the same term counts.
- New index, unchanged index, reindex, soft delete, HTTP 404/410 and `noindex` cases preserve document frequency.
- Concurrent rebuild/removal/update scenarios cannot reintroduce counts for removed documents.
- Unit tests and PostgreSQL smoke tests pass.
- Crawler lock contention and deadlocks are measured before scaling workers.

## Historical caution for future AI agents

**Do not recreate the abandoned independent vocabulary worker.** The vocabulary is intentionally derived from the indexer's *stored lexemes*. A redesign must show that it preserves transactional correspondence with `search_index`, manages historical backfill and all deletion paths, and avoids adding a second divergent tokenizer. Similarly, **do not delete the forward repair migration or replace it by editing already-applied revisions.**

---

This is **decision documentation**: why the architecture was chosen, alternatives considered, trade-offs, failures, and constraints. Implementation details and commands live in `docs/pr4-vocabulary-consistency.md`.
