# Developer's Eye: Vocabulary Consistency (PR #4)

**Document type:** Implementation / operations documentation (`docs/`)  
**Repository:** `nishchup489-afk/developers_eye`  
**Pull request:** [#4: fix: repair vocabulary consistency after PR #3](https://github.com/nishchup489-afk/developers_eye/pull/4)  
**Merged commit reviewed:** `c0d1690bef734447cd576046e3da2a5b023cbded`  
**Status:** Merged; runtime/database validation not independently verified. Two post-merge Codex review findings remain open.

## 1. Purpose and scope

PR #3 integrated a per-document vocabulary into the existing search index writer. PR #4 adds the missing infrastructure for maintaining that vocabulary consistently: a repair migration, a full backfill/recount, shared vocabulary-aware index deletion, and corresponding test updates.

**There is no additional vocabulary worker.** Existing `indexer` jobs continue to generate `search_vector` and `code_vector`; vocabulary is derived from the lexemes already stored in these PostgreSQL `TSVECTOR` columns. The new rebuild is a manually invoked CLI, not a daemon.

### Exact files changed in PR #4

| File (relative to repository root) | Change | Responsibility |
|---|---|---|
| `backend/alembic/versions/9a71c3fb20d4_ensure_search_terms.py` | Added | Ensure the `search_terms` schema and trigram index exist. |
| `crawler/src/indexer/vocabulary.py` | Modified | Add shared advisory lock and indexed-document deletion helper. |
| `crawler/src/indexer/vocabulary_rebuild.py` | Added | Recompute all term document frequencies from existing index vectors. |
| `crawler/src/indexer/writer.py` | Modified | Coordinate index writes with the vocabulary mutex; use shared removal helper. |
| `crawler/src/crawler/worker/jobs/utility.py` | Modified | Decrement vocabulary on HTTP 404/410 and `noindex` removals. |
| `crawler/tests/indexer/test_indexer.py` | Modified | Isolate vocabulary in a temp table; add frequency and rebuild assertions. |
| `crawler/tests/indexer/test_service_writer.py` | Modified | Update mocks for the new lock and deletion helper. |

**Not changed in PR #4:** `indexer/repository.py`, `backend/models/search_terms.py`, and the underlying `vocabulary_terms()` / `synchronize_vocabulary()` algorithms. Those were already present, chiefly from PR #3.

## 2. Data model and vocabulary semantics

The existing SQLAlchemy model `backend/src/backend/models/search_terms.py` defines:

```sql
CREATE TABLE search_terms (
    term TEXT PRIMARY KEY,
    document_frequency INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT ck_search_terms_length CHECK (length(term) BETWEEN 1 AND 128),
    CONSTRAINT ck_search_terms_document_frequency CHECK (document_frequency >= 0)
);
CREATE INDEX ix_search_terms_trgm
    ON search_terms USING gin (term gin_trgm_ops);
```

The migration uses `public.search_terms`, `CREATE EXTENSION IF NOT EXISTS pg_trgm`, and `IF NOT EXISTS` for the table and index.

`document_frequency` means **number of indexed documents containing the normalized term at least once**, *not* number of occurrences across all documents. Each document contributes either zero or one to a term's frequency, even if the term appears repeatedly in its title, body, and code.

The input is a deduplicated union of lexemes from `search_index.search_vector` and `search_index.code_vector`, extracted using:

```sql
tsvector_to_array(search_vector || code_vector)
```

The previously existing `vocabulary_terms()` filter lowercases/casefolds lexemes, removes many malformed artifacts, and deduplicates them. English-configured vectors may contain stems such as `applic`, so **this vocabulary is an indexed-lexeme dictionary rather than a natural-language spelling dictionary**.

## 3. Indexing path (`writer.py`)

`persist_search_vectors(session_factory, vectors, indexed_hash)` owns the transaction:

```text
BEGIN
  ├─ lock_vocabulary(session)           [new in PR #4]
  ├─ lock Document row FOR UPDATE
  ├─ reject changed / unavailable source
  ├─ check indexed hash and timestamp
  ├─ if unchanged: return UNCHANGED
  ├─ read old index lexemes
  ├─ UPSERT search_index vectors
  ├─ read new index lexemes
  ├─ synchronize_vocabulary(old, new)
  └─ COMMIT
```

When the source is `STALE` or the index is `UNCHANGED`, it does not call `synchronize_vocabulary()`. Note that this implementation obtains the global advisory lock *before* knowing whether vocabulary will change, reducing concurrency.

### Example: updated document

```text
Old document terms: python, django, asyncio
New document terms: python, fastapi, asyncio

python   -> unchanged
asyncio  -> unchanged
django   -> document_frequency - 1
fastapi  -> document_frequency + 1
```

The existing `synchronize_vocabulary()` applies sorted per-term deltas. Increments use PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`. Decrements require an existing positive frequency, delete zero-frequency rows, and raise a drift error if the expected row is missing. A raised error aborts the writer transaction, rolling back index changes as well.

### Important distinction

The implementation uses a **single SQL transaction for index and vocabulary writes**, but the system has not been demonstrated to be free of all concurrency issues. The deletion path described below is missing the lock at one call site in this merged commit.

## 4. Shared advisory lock (`vocabulary.py`)

`lock_vocabulary(session)` executes:

```python
await session.execute(
    select(func.pg_advisory_xact_lock(7331090042))
)
```

This is a PostgreSQL **transaction-scoped advisory mutex**. It is released automatically when the transaction commits or rolls back. It is not a schema lock or a lock on each individual term.

Intended participants:

- Indexer `persist_search_vectors()`.
- Indexer `remove_search_index()` (**missing the lock in the reviewed merge; see Known Issues**).
- Crawler job finalization in `crawler/worker/jobs/utility.py`.
- Manual `rebuild_vocabulary()`.

Because the key is global, all participating operations serialize, even when they update different documents or terms. The crawler currently acquires it for every active finalization, not only when deleting index rows. These are material throughput concerns.

The lock only coordinates code paths that actually acquire the same advisory key. Direct SQL changes to `search_index` or `document`, and cascade deletes performed outside the shared helper, can still cause vocabulary drift.

## 5. Shared deletion helper (`vocabulary.py`)

### `remove_indexed_documents(session, document_ids) -> int`

Purpose: delete selected `search_index` rows **and** remove their contributions to the vocabulary in the caller's transaction.

Algorithm:

1. Deduplicate and sort positive integer document IDs.
2. Query each existing index's `document_id` and stored lexeme array, ordered by document ID.
3. For each indexed document, delete its `search_index` row.
4. Call `synchronize_vocabulary(old_lexemes, new_lexemes=())` to decrement its terms.
5. Return the count of index rows actually processed; absent rows do not contribute to the result.

The helper **does not** open/commit/rollback a transaction, obtain the advisory mutex itself, verify that a source document is unavailable, or automatically lock `Document` rows. Those responsibilities belong to callers. The function's docstring requires relevant `Document` rows to be locked in ascending order.

### `remove_search_index()` in the indexer writer

The writer now invokes `remove_indexed_documents(session, [document_id])` instead of simply deleting the index row. Statuses remain:

| Status | Meaning |
|---|---|
| `STALE` | The document exists and is currently available, so deletion is rejected. |
| `REMOVED` | An index row was deleted. |
| `SKIPPED` | No index row remained. |

**Known defect:** this specific writer path does not call `lock_vocabulary()` before locking the source row, despite the shared mutex requirement.

## 6. Crawler deletion paths (`crawler/worker/jobs/utility.py`)

PR #4 changes the existing `_finalize()` transaction. After validating the target lease/transition, the code calls `lock_vocabulary(session)` before entering the deletion-handling branches.

### HTTP 404 / 410

The crawler:

1. Marks matching documents (via `last_crawl_target_id`) as unavailable, storing the HTTP status and timestamp.
2. Obtains their IDs from `UPDATE ... RETURNING Document.id`.
3. Calls `remove_indexed_documents(session, unavailable_ids)` instead of directly deleting `SearchIndex` rows.
4. Commits the source-state change, index removal and vocabulary deltas together.

The source `Document` row remains stored as unavailable; its search index is removed.

### `noindex`

The crawler:

1. Computes normalized/canonical URLs from documents rejected by the processing pipeline for `SkipReason.NOINDEX`.
2. Selects matching `Document` IDs with `ORDER BY Document.id FOR UPDATE`.
3. Calls `remove_indexed_documents(session, deleted_ids)` to remove their search indexes and decrement frequencies.
4. Deletes the matching `Document` rows, allowing any remaining database foreign-key cascades to run.

A `noindex` page therefore has its source document deleted in this path, while a 404/410 page is retained but marked unavailable. This is the behavior of the current code, not a recommended universal search-engine policy.

### Throughput implication

The mutex is currently acquired unconditionally for an active crawler finalization, even when no document is removed. The resulting serialization can be measured and reduced in a later change. Do not assume multiple crawler workers can finalize fully independently while this lock remains broad.

## 7. Rebuild and historical backfill (`vocabulary_rebuild.py`)

`rebuild_vocabulary(session_factory) -> tuple[int, int]` provides both initial backfill and a corrective recount. It is a **one-time CLI**, not a service/worker.

Within one transaction it:

1. Acquires `lock_vocabulary(session)`.
2. Streams all existing `search_index` rows in `document_id` order.
3. Extracts combined `TSVECTOR` lexemes and filters/deduplicates them for each document.
4. Accumulates `Counter[term] += 1` for each unique term per document.
5. Deletes all rows from `search_terms`.
6. Inserts the recomputed rows in batches of **500 terms**.
7. Commits, then reports the number of indexed documents and distinct terms.

Example output format:

```text
Rebuilt vocabulary: <indexed document count> indexed documents; <distinct term count> unique terms
```

The transaction protects the replacement from leaving a partially populated table if a database error occurs, but may run for an extended period and hold memory proportional to the number of distinct terms. Indexer and crawler writers should be stopped during the first migration/backfill. Run against a backup-capable environment.

The rebuild **does not** fetch pages, tokenize raw source text, regenerate the `TSVECTOR`s, or touch `indexed_hash`.

It can be rerun to repair frequency drift, but a rebuild cannot recover information for search-index rows that were already deleted.

## 8. Database migration

New file: `backend/alembic/versions/9a71c3fb20d4_ensure_search_terms.py`.

- Revision: `9a71c3fb20d4`.
- Down-revision: `da03da123834`.
- Installs `pg_trgm` if available and permitted.
- Creates `public.search_terms` if absent.
- Creates `ix_search_terms_trgm` if absent.
- `downgrade()` is deliberately a no-op, to avoid dropping a table that may have been created manually before this repair migration.

The older `4f9fab47f6a0` and `da03da123834` migrations had empty upgrade bodies. This new **forward repair revision** was chosen because those older revisions could already have been stamped as applied in user databases.

**Caution:** `CREATE TABLE IF NOT EXISTS` will not validate or repair the schema of an existing table with the same name. Verify model/table compatibility if it existed before migration. `CREATE EXTENSION` may require appropriate database permissions.

## 9. PostgreSQL and writer tests

### `crawler/tests/indexer/test_indexer.py`

- Adds a temporary `search_terms` table to the existing per-connection TEMP fixtures.
- Asserts `python` gets document frequency 1 on the first indexed document.
- After a source update, asserts new term `quasarwhim` has frequency 1.
- After soft-unavailable removal, asserts the temporary vocabulary becomes empty.
- Calls `rebuild_vocabulary()` and verifies it sees one document and at least one term.
- Deletes the remaining index with `remove_indexed_documents()` and verifies vocabulary becomes empty before source hard-delete.

It requires a PostgreSQL connection through `TEST_DATABASE_URL`; otherwise the database smoke test is skipped. The fixture does not itself create a disposable database; use a database dedicated to tests.

### `crawler/tests/indexer/test_service_writer.py`

- Mocks `lock_vocabulary` for several writer cases.
- Mocks the new `remove_indexed_documents()` function for removal cases.
- Keeps checks for stale document revisions, unchanged hashes, version refresh and removal status handling.

**Known defect:** `test_writer_unchanged_index()` omitted the new lock mock. Its `FakeSession` lacks `.execute()`, so this test is expected to fail with `AttributeError` unless fixed.

## 10. Operational runbook (Windows PowerShell)

**Preconditions:** The correct local branch has been updated, outstanding file conflicts have been resolved, and a verified PostgreSQL backup exists. Do not run migration/backfill while crawler/indexer writers are actively mutating the same database.

At repository root, first examine the checkout:

```powershell
git status
git branch --show-current
git log -1 --oneline
```

After you have safely committed or stashed local edits and checked out `main`, update it:

```powershell
git pull --ff-only origin main
```

Stop the crawler and indexer worker processes, then apply the repair migration from `backend/`:

```powershell
cd backend
poetry run alembic upgrade head
poetry run alembic current
```

Recount the vocabulary from stored search-index lexemes from `crawler/`:

```powershell
cd ../crawler
poetry run python -m indexer.vocabulary_rebuild
```

Inspect PostgreSQL:

```sql
SELECT COUNT(*) AS indexed_documents FROM search_index;
SELECT COUNT(*) AS vocabulary_terms FROM search_terms;
SELECT term, document_frequency
FROM search_terms
ORDER BY document_frequency DESC, term
LIMIT 25;
SELECT COUNT(*) AS invalid_frequencies
FROM search_terms
WHERE document_frequency <= 0;
```

Expected: a nonempty vocabulary when eligible indexed lexemes exist, no nonpositive frequencies after a successful rebuild, and plausible term distribution. The `search_terms` row count need not equal the number of indexed documents.

Run unit tests from `crawler/`:

```powershell
poetry run pytest tests/indexer/test_vocabulary.py tests/indexer/test_service_writer.py -v
```

Run the optional PostgreSQL integration test **only with a disposable test database** configured in `TEST_DATABASE_URL`:

```powershell
poetry run pytest tests/indexer/test_indexer.py -v -rs
```

The merge did not have a verified passing PostgreSQL/CI run, and the unchanged-index unit test has a known defect. The commands above are validation steps, not assertions that the tests pass.

## 11. Known limitations and failure modes at merged commit

1. **Missing deletion mutex (Codex P2, outstanding):** `indexer/writer.py::remove_search_index()` does not call `lock_vocabulary()` before a removal. A concurrent rebuild can produce inaccurate frequencies. [Review](https://github.com/nishchup489-afk/developers_eye/pull/4#discussion_r4434088290).
2. **Missing unit-test lock mock (Codex P2, outstanding):** `test_writer_unchanged_index()` uses `FakeSession` without `execute()`. [Review](https://github.com/nishchup489-afk/developers_eye/pull/4#discussion_r4434088292).
3. **Global lock contention:** index writes, rebuilds and every active crawler finalization contend on one mutex. Measure throughput and lock wait time before scaling.
4. **Unmanaged SQL/cascades:** manual SQL deletes and cascades executed outside the shared helper do not automatically decrement vocabulary. Rebuild after such maintenance.
5. **Per-term statement overhead:** ordinary `synchronize_vocabulary()` issues SQL operations per changed term; this may become expensive on very large documents or high update throughput.
6. **Historical deployment sequence:** executing the indexer writer before applying the table migration/backfill can cause failed indexing or drift errors.
7. **Alembic model registry:** `backend/models/__init__.py` does not import `SearchTerm` in this snapshot. The manual SQL repair migration works independently, but future autogeneration may not see that model unless imported into metadata registration.
8. **Unverified execution:** neither passing PostgreSQL smoke tests nor successful deployment are established by the merged PR alone.

## 12. Troubleshooting

| Symptom | Likely cause | Response |
|---|---|---|
| `relation "search_terms" does not exist` | Repair migration not applied in the configured DB. | Stop workers; verify database URL and `alembic current`; apply upgrade. |
| `function ... gin_trgm_ops does not exist` / migration extension error | `pg_trgm` absent or insufficient permissions. | Have the database administrator enable the extension and rerun migration. |
| `Vocabulary count drift detected for 'term'` | Historical rows were not backfilled, a deletion bypassed synchronization, or concurrent races occurred. | Stop writers; inspect the affected DB; run an authoritative rebuild; fix bypass path. |
| `test_writer_unchanged_index` raises `AttributeError` | Missing `lock_vocabulary` AsyncMock in the test. | Fix the known mock omission. |
| Throughput degrades during crawling | Global advisory mutex acquired by all finalization paths. | Profile lock waits; narrow lock acquisition to actual vocabulary mutations. |
| PR merged but the local file differs | Local uncommitted changes or branch mismatch. | `git status` and `git diff`; preserve local work before updating. |

## 13. Related code and review references

- [PR #3, initial vocabulary integration](https://github.com/nishchup489-afk/developers_eye/pull/3)
- [PR #4, consistency repairs](https://github.com/nishchup489-afk/developers_eye/pull/4)
- `crawler/src/indexer/repository.py` (PR #3): `get_index_lexemes()` and index UPSERT.
- `backend/src/backend/models/search_terms.py` (preexisting): model/schema of the vocabulary table.
- `crawler/src/indexer/vocabulary.py`: frequency deltas, global mutex and deletion helper.
- `crawler/src/indexer/vocabulary_rebuild.py`: authoritative recount.

---

This is **mechanics documentation**: how the implementation operates, how to run it, and what can fail. Architectural choices and rejected alternatives are recorded separately in `tech_docs/adr-vocabulary-consistency-pr4.md`.
