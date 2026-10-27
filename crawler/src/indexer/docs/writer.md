# Developer's Eye: Transactional index writer

**Module:** `crawler/src/indexer/writer.py`  
**Public API:** `persist_search_vectors()`, `remove_search_index()`  
**Storage:** `backend.models.search_index.SearchIndex` via `indexer.repository`.

## Purpose

The writer is the **single transaction authority** for search-index synchronization. `vector.py` produces *unevaluated SQLAlchemy expressions*. The writer decides whether those expressions can safely be executed against the current document revision. It delegates SQL operations to `repository.py`.

```text
service.py: SearchVectors + indexed_hash
                |
                v
writer.persist_search_vectors()
  OPEN TRANSACTION
    |-- repository.get_document_for_update()  [SELECT ... FOR UPDATE]
    |-- verify source exists + is_available + source_id + updated_at
    |-- repository.get_search_index()          [read hash, indexed_at]
    |-- if same hash and current timestamp: UNCHANGED
    |-- else repository.upsert_search_index()  [INSERT ... ON CONFLICT UPDATE]
  COMMIT / ROLLBACK
                |
                v
            IndexStatus
```

**The document row lock must remain held until UPSERT and commit are complete.** The lock protects the interval between checking source freshness and storing a vector. The repository and service should not independently commit or close this transaction.

## `persist_search_vectors(session_factory, vectors, *, indexed_hash) -> IndexStatus`

### Input contract

- `session_factory`: SQLAlchemy `async_sessionmaker[AsyncSession]`; **not a shared session**.
- `vectors`: `SearchVectors` with `document_id`, `source_id`, `source_updated_at`, and `text_vector`/`code_vector` expressions.
- `indexed_hash`: nonempty string; the repository further validates `vN:<64 lowercase hex digits>`.

### Decision process

| Condition under the document lock | Action/status |
|---|---|
| Source row missing | `STALE` (no UPSERT) |
| Source unavailable | `STALE` (no UPSERT) |
| Source ID differs | `STALE` (no UPSERT) |
| `source.updated_at != vectors.source_updated_at` | `STALE` (no UPSERT) |
| Existing hash matches **and** `indexed_at >= source.updated_at` | `UNCHANGED` (no UPSERT) |
| Otherwise | UPSERT both vectors and the hash; `INDEXED` |

The writer opens `async with session_factory() as session`, then `async with session.begin()`. Normal exit commits, exceptions roll back. Early returns inside the transaction context still properly close the context and finish the transaction.

The UPSERT maps:

| `SearchVectors` field | PostgreSQL column |
|---|---|
| `text_vector` | Existing `search_index.search_vector` |
| `code_vector` | New `search_index.code_vector` |
| `indexed_hash` argument | `search_index.indexed_hash` |
| Computed transaction time | `search_index.indexed_at` |

Vector expressions are evaluated by PostgreSQL during the UPSERT. Python does not compute lexemes, stemming, weights, or GIN entries.

### Example

```python
from backend.db.session import SessionFactory
from indexer.writer import persist_search_vectors

# 'vectors' came from build_search_vectors(analyzed, config=config).
# 'indexed_hash' came from calculate_index_hash(index_doc, config=config).
status = await persist_search_vectors(
    SessionFactory,
    vectors,
    indexed_hash=indexed_hash,
)
```

## `remove_search_index(session_factory, document_id) -> IndexStatus`

For soft-unavailable documents, `selector.select_removal_candidates()` finds existing index records. The writer opens a transaction and locks the current document if it still exists.

- **Available source:** return `STALE`, preserving its searchable index.
- **Unavailable source or missing document:** delegate `delete_search_index()`; return `REMOVED` if the row existed, otherwise `SKIPPED`.
- **Hard-deleted document:** the existing foreign key `search_index.document_id REFERENCES document(id) ON DELETE CASCADE` should ordinarily remove its row automatically.

This operation is idempotent. A stale removal candidate cannot erase a revived document's index when the writer's locking contract is obeyed.

## Isolation and concurrency

**Supported discipline:** every component that changes index-relevant `Document` content updates `updated_at`; every index writer locks the source row before writing; deletion and availability updates use normal PostgreSQL transactional semantics.

1. Worker A prepares a snapshot at time `T1` without holding a row lock.
2. Crawler B changes the source to revision `T2` and commits.
3. Writer A locks the latest row and detects `T2 != T1`.
4. Writer A returns `STALE`, without writing obsolete vectors.
5. The selector discovers the newer revision on a subsequent scan.

A competing index writer obeying the same protocol queues on the source row lock; once acquired, it checks hash/timestamp again. This is how duplicate work avoids incorrect overwrites.

**Limits:** The writer does not manage deadlock retries, DB pool sizing, timeouts, indexing-queue leases, or worker concurrency. An exception during UPSERT is propagated; `session.begin()` rolls back the transaction. Use targeted retries in the worker for transient DB failures. The `Document.updated_at` invariant is essential, not optional.

## Database and version prerequisites

Your original `SearchIndex` model had only `search_vector`. The two-vector pipeline needs:

- `SearchIndex.code_vector` mapped as a PostgreSQL `TSVECTOR`.
- Alembic migration adding `code_vector` and a GIN index.
- `repository.upsert_search_index()` writing `search_vector` and `code_vector`.
- `INDEXER_INDEX_VERSION` incremented on vector format changes, so older indexes are rebuilt.

Verify the current Alembic head before applying migrations. The test suite's TEMP-table test does **not** prove that the persistent production schema has been migrated.

## Final testing strategy

From `crawler/`:

```powershell
# Mocked service/writer unit tests
poetry run pytest src/indexer/tests/test_service_writer.py -v

# Real builder/analyzer/vector transformations (no DB), plus a separate
# PostgreSQL end-to-end test when TEST_DATABASE_URL is set
poetry run pytest src/indexer/tests/test_final_indexer.py -v -rs
```

In PowerShell, set the optional Postgres test connection:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@localhost:5432/developers_eye_test"
poetry run pytest src/indexer/tests/test_final_indexer.py -v -rs
Remove-Item Env:TEST_DATABASE_URL
```

The integration test creates PostgreSQL **TEMP `document` and `search_index` tables** on a dedicated connection; these shadow persistent tables and disappear after that connection closes. It verifies new indexing, actual English/simple lexemes, unchanged hash, stale rejection, source update, version upgrade, soft removal, revival, and hard-delete cascade. It does not run Alembic or touch real application content.

**Expected if the variable is absent:** local transformation test passes, PostgreSQL end-to-end test skips. The skipped result is not a production integration pass.
