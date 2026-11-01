---
id: ADR-0002
title: Fuzzy vocabulary is a projection of stored index lexemes, kept in the index writer's transaction
status: accepted
date: 2026-10-31
area: indexer
feature: vocubulary
code:
  - crawler/src/indexer/vocabulary.py:vocabulary_terms
  - crawler/src/indexer/vocabulary.py:synchronize_vocabulary
  - crawler/src/indexer/vocabulary.py:lock_vocabulary
  - crawler/src/indexer/vocabulary.py:remove_indexed_documents
  - crawler/src/indexer/writer.py:persist_search_vectors
  - crawler/src/indexer/writer.py:remove_search_index
  - crawler/src/indexer/repository.py:get_index_lexemes
  - crawler/src/indexer/vocabulary_rebuild.py:rebuild_vocabulary
  - crawler/src/crawler/worker/jobs/utility.py:_finalize
  - backend/src/backend/models/search_terms.py
supersedes:
superseded_by:
related: [INC-0001]
---

# ADR-0002: Fuzzy vocabulary is a projection of stored index lexemes

## TL;DR
`search_terms(term, document_frequency)` is filled from the lexemes already stored in `search_index.search_vector || code_vector`, not by tokenizing documents again. The index writer applies +1/-1 deltas for the terms a document gained or lost in the same transaction as the `search_index` upsert or delete, so the index and the vocabulary commit or roll back together. A one-shot rebuild CLI recounts everything from the stored vectors for backfill and drift repair.

## Context
Typo-tolerant search needs a dictionary of indexed terms with document frequencies, so a misspelled query word can be matched against `search_terms` with `pg_trgm` and an edit-distance check (`backend/search/retrieval/fuzzy/`).

The first plan was a separate package, `crawler/src/retrieval_vocabulary/` (config, selector, builder, repository, tokenizer, normalizer, writer, worker). It had its own selector that picked indexed documents by `indexed_hash`, re-read their text (`title`, `body`, `headings`, `code_blocks`, `tags`) and tokenized it a second time. About 1,700 lines were written and then deleted in commit `a8b1b03` ("was going in wrong direction ... replanned").

> **Question for nish:** what made you stop the `retrieval_vocabulary` worker? Was it the second tokenizer disagreeing with Postgres, the extra selector/lease work, or something you hit while testing? One or two sentences here will stop the next person from rebuilding it.

PR #3 (`d603836`, `cc30210`, `0f078af`) moved vocabulary maintenance into the existing index writer. Review of PR #3 found four gaps: the table migration was empty (INC-0001), already-indexed documents had no counts, crawler deletion paths deleted index rows without decrementing, and the Postgres smoke test wrote to the real vocabulary table. PR #4 (`c0d1690`) fixed those with a repair migration, the rebuild CLI, the shared removal helper and a global advisory lock.

Constraints:
- The fuzzy matcher must only suggest terms that the index can actually match, so the dictionary has to use the same tokenization as `search_index` (`english` for prose, `simple` for code).
- The vocabulary must not drift from `search_index`; a drift turns into wrong suggestions or a `RuntimeError` on decrement.
- Index rows are removed from three places: the indexer (`remove_search_index`), the crawler on HTTP 404/410, and the crawler on `noindex`.

## Decision
1. **Source of terms.** `get_index_lexemes()` reads `tsvector_to_array(search_vector || code_vector)` for one document. `vocabulary_terms()` casefolds, deduplicates and filters them: length 2 to 64, must match `[a-z][a-z0-9_+.#-]*` (plus `c++`, `c#`, `f#`, `.net`), no trailing `.`/`-`/`_`, at most one dot and two hyphens, no archive extensions (`zip`, `tar`, `gz`, `tgz`, `pdf`, `epub`, `whl`), at least two letters, and not mostly digits.
2. **Meaning of a count.** `document_frequency` is the number of indexed documents that contain the term at least once, not the number of occurrences.
3. **Writes happen in the index writer's transaction.** `persist_search_vectors()` reads the old lexemes, upserts `search_index`, reads the new lexemes, then calls `synchronize_vocabulary(old, new)`. Only the difference is written: terms in `new - old` get `INSERT ... ON CONFLICT DO UPDATE SET document_frequency = document_frequency + 1`, terms in `old - new` get `UPDATE ... SET document_frequency = document_frequency - 1 WHERE document_frequency > 0 RETURNING`, and a row that reaches 0 is deleted. A missing row on decrement raises `RuntimeError("Vocabulary count drift ...")`, which rolls back the index write too.
4. **One removal helper.** `remove_indexed_documents(session, ids)` deletes `search_index` rows and decrements their terms in the caller's transaction. The indexer removal path and both crawler deletion paths (404/410 marks the document unavailable, `noindex` deletes the document) call it.
5. **One global lock.** `lock_vocabulary()` takes `pg_advisory_xact_lock(7331090042)`. It is taken first, before any `document` row lock, by `persist_search_vectors()`, by every crawler `_finalize()` transaction, and by the rebuild.
6. **Backfill and repair.** `python -m indexer.vocabulary_rebuild` streams every `search_index` row in one transaction under the lock, counts terms in memory, deletes all of `search_terms` and inserts the new counts in batches of 500. It is a maintenance command, not a worker.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Projection of stored lexemes, deltas in the index writer's transaction, rebuild CLI | Same tokens as the index; index and vocabulary commit together; no new worker | Every deletion path must use the helper; one global lock; counts can still drift through raw SQL or cascades | chosen |
| B. Separate `retrieval_vocabulary` worker that re-tokenizes document text | Decoupled from the indexer | A second tokenizer that can disagree with Postgres; its own selector and freshness rules; the vocabulary lags the index | rejected: built and deleted in `a8b1b03` |
| C. Recount on a schedule only (no deltas) | Simple; always self-consistent after a run | Stale between runs; a full scan per run | rejected for normal operation; kept as the rebuild CLI |
| D. Full reindex to backfill counts | Uses the normal write path | Recomputes every vector when the lexemes are already stored; touches `indexed_hash` for no reason | rejected |
| E. Per-term or per-document locks instead of one advisory lock | Writers on different documents don't wait for each other | Needs a careful lock order and a different way to stop the rebuild racing writers | not done yet (see Revisit when) |
| F. Database trigger on `search_index` that maintains `search_terms` | Every path, including raw SQL and cascades, stays consistent | Logic moves into SQL; harder to test from Python | not considered in PR #4 |

> **Question for nish:** did you look at a trigger on `search_index` (option F)? It would also cover cascade deletes and manual SQL, which the helper cannot. If you rejected it, say why.

## Why
- **Correctness.** The matcher should only suggest strings the index can match. English vectors store stems (`applic`, not `application`), so a dictionary built from raw text would suggest words that then miss in `websearch_to_tsquery('english', ...)`. Reading the stored lexemes avoids that by construction.
- **Consistency.** Index row and vocabulary delta are in one transaction. Either both commit or neither does, and a missing row on decrement is treated as corruption, not ignored.
- **Cost.** Only changed terms are written. An unchanged re-index (`UNCHANGED`) writes nothing; an update that changes two terms writes two rows.
- **Cost to build.** No new process, selector or lease table. The rebuild reuses the same filter.

## Consequences
- Gained: suggestions stay in step with the index; vocabulary changes are visible at the same moment as index changes.
- Accepted limitations:
  - Suggestions are index lexemes, including stems. Correction only rewrites plain alphabetic words of 4 to 32 letters, so this mostly matters for English words.
  - Any path that deletes `search_index` rows without `remove_indexed_documents()` (manual SQL, a hard `DELETE FROM document` that cascades) leaves counts too high. Run the rebuild afterwards.
  - The global advisory lock serializes every index write, every crawler finalization and the rebuild, even when they touch different terms (see `issues.md`).
  - One SQL statement per removed term.
- What depends on this: `backend/search/retrieval/fuzzy/` (reads `search_terms`), the admin vocabulary report (`backend/services/vocabulary_reporting.py`, which flags terms whose frequency is greater than the number of indexed documents as drift).

## Invariants
- One indexed document adds at most 1 to any term's `document_frequency`.
- Every `search_index` upsert that changes the lexeme set updates `search_terms` in the same transaction.
- Every `search_index` delete goes through `remove_indexed_documents()` in the same transaction as the delete.
- `document_frequency >= 0`, and rows at 0 are deleted.
- Vocabulary-changing transactions take `lock_vocabulary()` before any `document` row lock.
- `vocabulary_terms()` is the only filter; the writer and the rebuild both use it.

## Failure modes
- **Over-count when a document adds more than one new term (open, found 2026-10-31).** In `synchronize_vocabulary()` the `for term in sorted(changes)` loop re-runs the upsert for the whole `added` list once per added term. A document that adds k new terms raises each of them by k instead of 1. `test_addition_issues_conflict_safe_upsert` only adds one term, so it does not catch this. The rebuild CLI produces correct counts, but normal indexing inflates them again. Fix: run the batch upsert once, outside the loop, and add a test with two or more new terms.
- **`remove_search_index()` does not take `lock_vocabulary()`** (open, PR #4 review). A removal can run during a rebuild and leave the rebuilt counts off by that document. Fix: call `lock_vocabulary()` before `get_document_for_update()`.
- **Counts were never seeded.** Documents indexed before PR #3 have no counts, so their first decrement raises the drift error. Run the rebuild once after applying the migration.
- **Long rebuild.** The rebuild holds the global lock and keeps every distinct term in memory for the whole scan. Stop the crawler and indexer before running it.

## Evidence
- Tests:
  - `crawler/src/indexer/tests/test_vocabulary.py`: the filter keeps developer terms and drops artifacts; unchanged lexemes write nothing; decrement to 0 deletes; a missing row raises.
  - `crawler/src/indexer/tests/test_indexer.py` (Postgres, `TEST_DATABASE_URL`, temp `search_terms` table): counts after first index, after an update, after soft removal; rebuild finds one document; shared removal empties the vocabulary.
  - `crawler/src/indexer/tests/test_service_writer.py`: lock and helper are called.
- Measured: rebuild of 15,600 documents into 18,432 terms in about 6 s (sample log in `crawler/src/indexer/operations.md`).

  > **Question for nish:** is that log from a real run on your database, or an illustrative example? If real, add the machine and Postgres version.
- Assumed: lock contention from the global advisory lock is acceptable at the current worker counts. Not measured.
- Commits: `a8b1b03` (abandoned worker deleted), `d603836`, `cc30210`, `0f078af` (PR #3), `c0d1690` (PR #4), `e5bf772` (rebuild progress output, PR #5).
- Longer write-ups: `crawler/src/indexer/docs/adr-vocabulary-consistency-pr4.md`, `crawler/src/indexer/docs/pr4-vocabulary-consistency.md`.

## Revisit when
- Indexer or crawler throughput stops scaling with workers and `pg_locks` shows sessions waiting on advisory lock `7331090042`.
- A new path needs to delete `search_index` rows in bulk (retention, source removal), or cascade deletes become common. Consider a trigger (option F).
- Fuzzy correction needs whole words instead of stems (for example suggesting `application` rather than `applic`). That needs a different term source.
- The rebuild takes longer than the maintenance window you can stop workers for.

## Rules for future changes
- Do not tokenize document text to build the vocabulary. Read lexemes from `search_index` (`get_index_lexemes()` or the same `tsvector_to_array` expression).
- Never delete `search_index` rows directly. Use `remove_indexed_documents()` inside a transaction that already holds `lock_vocabulary()`.
- Take `lock_vocabulary()` before locking any `document` row.
- Change `vocabulary_terms()` only together with a rebuild, or old and new terms will be counted differently.
- Do not recreate a separate vocabulary worker without a new ADR.
- After manual SQL on `search_index` or `document`, run `python -m indexer.vocabulary_rebuild --once` with workers stopped.
- Tests that must keep passing: `indexer/tests/test_vocabulary.py`, `indexer/tests/test_service_writer.py`, `indexer/tests/test_indexer.py` (with `TEST_DATABASE_URL`).
