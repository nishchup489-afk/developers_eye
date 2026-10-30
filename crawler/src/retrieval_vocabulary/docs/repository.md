# `repository.py` · Where does the database work happen?

**Purpose:** Own all PostgreSQL/SQLAlchemy queries. Selection policy stays in `selector.py`.

- `fetch_pending_sync_rows()` joins `document`, `search_index`, and `vocabulary_document_state`. It selects successfully indexed documents whose vocabulary revision is missing or outdated.
- `fetch_pending_removal_ids()` selects previously processed documents whose index/source is missing or unavailable.

Both methods use `document_id > after_document_id`, ordered ascending, plus `LIMIT`, so the worker can process many documents in batches.

Both methods are **read-only**: no commit, no delete, no frequency changes, and no row locking. Transactions and concurrency-safe writes belong in `writer.py`.

**Future:** Add term membership, count update, and processed-revision write queries to this repository. Keep them atomic under the writer's transaction.
