# Developer's Eye indexer service + writer

## Paths

- `crawler/src/indexer/service.py`: performs a single candidate's build/hash/analyze/vector pipeline and delegates transactional writes.
- `crawler/src/indexer/writer.py`: checks freshness while holding `SELECT FOR UPDATE` on the document, skips current indexes, inserts/updates through the repository, and removes only obsolete records.
- `crawler/src/indexer/tests/test_service_writer.py`: fast unit tests with mocked database operations.

## Dependencies

These files target your existing `indexer.builder`, `indexer.analyzer`, `indexer.vector`, `indexer.schemas`, `indexer.config`, and the previously supplied `indexer.repository` implementation (`get_document_for_update`, `get_search_index`, `upsert_search_index`, `delete_search_index`). Your existing GitHub branch still has an empty `repository.py`; copy or implement it before running these files.

The previous repository implementation expects two columns: existing `search_vector` and newly added `code_vector`. Apply the previously supplied Alembic migration and update the `SearchIndex` ORM model before processing documents. Do not apply a migration without confirming current Alembic head and database backup.

## Usage

```python
from backend.db.session import SessionFactory
from indexer.config import IndexerConfig
from indexer.schemas import IndexCandidate
from indexer.service import index_candidate, remove_candidate

config = IndexerConfig(index_version=2)
result = await index_candidate(SessionFactory, candidate, config=config)
# result.status is an IndexStatus

removed = await remove_candidate(SessionFactory, document_id)
```

`IndexCandidate` objects should come from `select_index_candidates()`. Removals should come from `select_removal_candidates()`.

## Tests

From `crawler/`:

```powershell
poetry run pytest src/indexer/tests -v -rs
```

`test_service_writer.py` uses mocks and does not connect to PostgreSQL. `test_indexer.py` adds an opt-in end-to-end lifecycle test against PostgreSQL TEMP tables when `TEST_DATABASE_URL` is set. See [tests/README.md](tests/README.md) for setup and [tests/test_case.md](tests/test_case.md) for what each test covers.

Still not covered before production deployment: concurrent writers, a source update while waiting on the lock, and the `code_vector` schema migration.

## Status and failures

- `INDEXED`: vectors persisted.
- `UNCHANGED`: existing indexed hash matches and indexed timestamp is current.
- `STALE`: source changed or disappeared; reselect a new candidate.
- `REMOVED`: obsolete index record removed.
- `SKIPPED`: no index record existed to remove.
- `FAILED`: invalid source input; details describe validation error.

SQLAlchemy and unexpected exceptions propagate to the worker. The worker owns logging, retries and backoff. The service does not claim work, create worker pools, or handle cursors.

**Freshness invariant**: index-relevant document changes must update `Document.updated_at`, and the writer's source lock and UPSERT must use one transaction. If this invariant is broken, indexing can serve stale data. The PostgreSQL `indexed_at` timestamp should be recorded on actual persist and compare correctly to the source revision. A document with bad data will be selected repeatedly unless the worker implements a failure/backoff policy.
