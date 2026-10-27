# Developer's Eye indexer operations

## Topology

`crawler.worker.runner` and `indexer.worker.runner` are **separate processes**
with separate database sessions. Both share PostgreSQL. There is no direct
RPC/HTTP communication: crawler updates `document`, and the indexer detects
missing, stale and old-version rows using `selector.py`.

## Modules

| Module | Responsibility | Writes DB? |
| --- | --- | --- |
| `reporting.py` | Calculate coverage and backlog from DB state | No |
| `reindex.py` | Request explicit rebuild by invalidating index metadata | Yes, hash metadata only |
| `worker/runner.py` | Select pages, execute service functions, log outcomes, poll | Via service/writer |

`service.py` builds an indexable snapshot and invokes `writer.py`.
`writer.py` owns transactions and source freshness checks. `repository.py`
performs individual SQL operations. Runner never shares one `AsyncSession`
across parallel jobs.

## Reindex semantics

- `--document-id 42` marks an existing searchable row with
  `indexed_hash = 'reindex:pending'`. Existing `TSVECTOR`s remain intact.
- Missing indexes are already eligible for indexing and do not need marking.
- Unavailable documents are excluded from reindex; removal handles them.
- `--all` marks existing available indexes in transaction-sized batches.
- `--dry-run` reports eligible rows without mutating them.
- This is **not** a durable work queue and does **not** synchronously rebuild.
- Index version upgrades are best handled by incrementing `INDEXER_INDEX_VERSION`
  and restarting indexer processes. This causes old-version rows to be selected
  without a mass metadata update.
- Avoid overlapping `--all` operations. Row locks serialize marking with
  writer updates, but marking can cause an intentional redundant rebuild.

## Reporting definitions

- `current_documents`: available documents with an index whose `indexed_at`
  is >= source `updated_at` and whose hash starts with the active version.
- `missing_documents`: available documents without an index row.
- `stale_documents`: available documents with an existing index row that fails
  either freshness criterion (including `reindex:pending`).
- `pending_documents`: missing + stale.
- `unavailable_index_rows`: soft-unavailable documents still indexed.
- `indexed_rows`: all rows in `search_index` (includes potentially stale rows).

The report is **point-in-time**, based on two read queries. It does not claim
failures, throughput, p95 duration, or historical outcomes; those need worker
logs or persisted telemetry. It does not lock the table or hold a consistent
snapshot over both statements at READ COMMITTED isolation.

## Execution

From PowerShell in `C:\Users\nishc\Documents\developers-eye\crawler`:

```powershell
# One bounded pass (one indexing page + one removal page)
poetry run python -m indexer.worker.runner --once --batch-size 5 --concurrency 2

# Continuous worker (Ctrl+C to stop)
poetry run python -m indexer.worker.runner --forever --batch-size 100 --concurrency 2 --poll-seconds 10

# Read-only JSON coverage report
poetry run python -m indexer.reporting

# Reindex a single document (preview, then mark)
poetry run python -m indexer.reindex --document-id 42 --dry-run
poetry run python -m indexer.reindex --document-id 42

# Mark all existing indexes for rebuilding (caution: writes metadata)
poetry run python -m indexer.reindex --all --dry-run
poetry run python -m indexer.reindex --all --batch-size 100

# Unit tests
poetry run pytest src/indexer/tests/test_indexer_operations.py -v

# All indexer tests
poetry run pytest src/indexer/tests -v --tb=short
```

Use `INDEXER_INDEX_VERSION=2` only **after** deploying matching writer/vector
rules and the new database schema. Verify the `SearchIndex.code_vector`
Alembic migration was applied, and run `poetry install` after adding `indexer`
to the Poetry `packages` list.

## Limitations and operations policy

- There is no lease/claim table: with multiple indexer processes, preparation
  may run more than once. Writer row locks and hash checks protect persistence.
- Failures remain eligible on later passes; the keyset cursor prevents
  immediate repeated attempts within a scan. Stop and fix permanently invalid
  content rather than relying on retries forever.
- `--once` processes at most `batch_size` candidates **of each kind**.
- The runner catches per-item errors, logs them, and counts failures; database
  connection failure during batch selection aborts the process.
- Running `reporting.py` does not create an admin API endpoint. That can be
  added later using `get_indexer_report()` in your FastAPI admin router.
