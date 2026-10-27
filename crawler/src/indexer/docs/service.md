# Developer's Eye: Indexer service

**Module:** `crawler/src/indexer/service.py`  
**Public API:** `index_candidate()`, `remove_candidate()`  
**Inputs/outputs:** `IndexCandidate` → `IndexResult`  
**Dependencies:** builder, analyzer, vector, writer, `IndexerConfig`, `async_sessionmaker`.

## Purpose

`service.py` orchestrates **one indexing job at a time**. It does not execute PostgreSQL writes itself. The indexer worker is responsible for finding candidates, scheduling batches, retries, and logging. The service is responsible for preparing an individual candidate and asking the writer to persist it safely.

```text
Worker selects IndexCandidate(document_id, source_updated_at)
       |
       v
service.index_candidate(session_factory, candidate, config)
       |
       +-- READ SESSION -- build_index_document() --> IndexDocument
       |                (session closes; no row locks)
       |
       +-- calculate_index_hash() --> indexed_hash, e.g. v2:<SHA-256>
       +-- analyze_index_document() --> AnalyzedDocument
       +-- build_search_vectors() --> SearchVectors (SQL expressions)
       |
       +-- persist_search_vectors() --> writer transaction
       |
       v
IndexResult(document_id, status, duration_ms, indexed_hash?, details?)
```

`IndexCandidate` is a **hint**, not a claimed job or guarantee of freshness. Concurrent crawler updates can make it stale at any stage. The writer performs the authoritative check under a row lock.

## Public API

### `index_candidate(session_factory, candidate, *, config) -> IndexResult`

1. Validates argument types (`IndexCandidate`, `IndexerConfig`).
2. Records start time using `perf_counter()`.
3. Opens a read-only-in-intent `AsyncSession` using the supplied factory and reloads the selected revision via `build_index_document()`.
4. Closes the read session before expensive processing/persistence.
5. Computes the versioned `indexed_hash` from index-relevant input and index settings.
6. Converts the `IndexDocument` into weighted text/code fields using `analyze_index_document()`.
7. Constructs unevaluated SQLAlchemy `TSVECTOR` expressions using `build_search_vectors()`.
8. Calls `writer.persist_search_vectors()`, which owns the write transaction.
9. Returns `IndexResult` with final status, duration, and stored hash when applicable.

**Expected return statuses**:

| Status | Cause | Worker guidance |
|---|---|---|
| `INDEXED` | Writer inserted/rebuilt the index | Record success |
| `UNCHANGED` | Existing matching hash and current timestamp | No write needed |
| `STALE` | Selected source disappeared, became unavailable, or changed | Reselect a fresh candidate; do not blindly retry the same revision |
| `FAILED` | `IndexDocumentError`, including invalid content or document too large | Log and apply a deliberate quarantine/backoff policy |

`IndexDocumentError` and `StaleIndexSourceError` become results. Unexpected SQLAlchemy, programming, and cancellation exceptions **propagate** to the worker. The service does not swallow them, retry them, or commit anything.

### `remove_candidate(session_factory, document_id) -> IndexResult`

Validates a positive integer document ID and delegates to `writer.remove_search_index()`.

| Status | Meaning |
|---|---|
| `REMOVED` | Obsolete index row was deleted |
| `SKIPPED` | Index row was already absent |
| `STALE` | Source is currently available; delete request must not remove a live index |

`remove_candidate()` does **not** delete a `Document`. It only requests removal of its search-index entry.

### `_result(document_id, status, started_at, *, indexed_hash=None, details=None)`

Private helper constructing `IndexResult`. Uses `perf_counter()` for elapsed milliseconds, clamps time to nonnegative, and supplies the optional hash and explanation.

## Example invocation

```python
from backend.db.session import SessionFactory
from indexer.config import IndexerConfig
from indexer.selector import select_index_candidates
from indexer.service import index_candidate

config = IndexerConfig(index_version=2)

async with SessionFactory() as session:
    candidates = await select_index_candidates(session, config=config)

for candidate in candidates:
    outcome = await index_candidate(SessionFactory, candidate, config=config)
    print(candidate.document_id, outcome.status, outcome.duration_ms)
```

In production, the **worker** owns concurrency and failure handling. Each parallel service call must get its own `AsyncSession` through the session factory. Never share an `AsyncSession` across concurrent tasks.

## Transaction boundary and invariants

- Builder preparation uses its own read session and deliberately does not lock the document.
- `writer.py`, not `service.py`, begins and commits the write transaction.
- `Document.updated_at` **must change** for every index-relevant content/metadata change.
- `source_id`, `updated_at`, and `is_available` must match when the writer locks the current document.
- `indexed_hash` includes content and `index_version`. Increment `INDEXER_INDEX_VERSION` when changing analyzer weights, configurations, or vector rules.
- The stored index uses `search_vector` for text and `code_vector` for code. The `code_vector` column needs the corresponding ORM/model migration.

## Known boundaries

- The service neither creates worker tasks nor does batch selection.
- It does not reserve candidates across processes. Duplicate preparation is possible; writer serialization ensures correct persistence when all writers follow the same locking contract.
- Invalid documents can be reselected repeatedly unless the worker maintains a failure/backoff/quarantine mechanism.
- It returns the calculated hash on `UNCHANGED`/`INDEXED`, not a fully materialized vector.

## Tests

Quick unit tests (mocked DB):

```powershell
poetry run pytest src/indexer/tests/test_service_writer.py -v
```

Final pipeline test (unit path plus opt-in PostgreSQL TEMP-table lifecycle):

```powershell
poetry run pytest src/indexer/tests/test_final_indexer.py -v -rs
```

Set `TEST_DATABASE_URL` to run the live-PostgreSQL test. See `docs/writer.md` for isolation and schema prerequisites.
