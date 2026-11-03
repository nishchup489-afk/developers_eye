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
poetry run pytest tests/indexer/test_indexer_operations.py -v

# All indexer tests
poetry run pytest tests/indexer -v --tb=short
```

Use `INDEXER_INDEX_VERSION=2` only **after** deploying matching writer/vector
rules and the new database schema. Verify the `SearchIndex.code_vector`
Alembic migration was applied, and run `poetry install` after adding `indexer`
to the Poetry `packages` list.

## Vocabulary rebuild CLI

`indexer.vocabulary_rebuild` is a **one-time maintenance command** and runs
separately from the crawler and indexer workers. It recomputes
`search_terms.document_frequency` from the distinct lexemes in
`search_index.search_vector || search_index.code_vector`; it does not crawl
or reindex document text.

From `crawler/`, after applying the vocabulary Alembic migration:

```powershell
# Stop crawler and indexer writers before a rebuild.
poetry run python -m indexer.vocabulary_rebuild --once

# Log a scan checkpoint every 250 documents; insert 100 terms per batch.
poetry run python -m indexer.vocabulary_rebuild --once --progress-every 250 --write-batch-size 100

# Show all flags.
poetry run python -m indexer.vocabulary_rebuild --help
```

The CLI shares `RichHandler` logging conventions with
`indexer.worker.runner`:

```text
[22:15:01] VOCABULARY REBUILD START mode=once progress_every=1000 write_batch_size=500
[22:15:02] SCAN documents=1000 unique_terms=3200 duration=1.42s
[22:15:04] SCAN COMPLETE documents=15600 unique_terms=18432 duration=3.41s
[22:15:04] WRITE batch=1/37 terms=500/18432
...
[22:15:07] VOCABULARY REBUILD COMPLETE documents=15600 unique_terms=18432 duration=6.02s
```

The values above are illustrative, not measured results. Scan and write
messages mean **work is in progress**, not committed. `REBUILD COMPLETE`
is printed only after the database transaction commits. An exception logs
`REBUILD FAILED` with a traceback, rolls back, and exits with code 1.
Ctrl+C exits with code 130. `--once` is optional; there is no `--forever`
because incremental index writes already maintain vocabulary.

**Deployment note:** stop all crawler/indexer writers before running this
command. An outstanding index-deletion path in PR #4 does not yet participate
in the shared advisory lock; a concurrent removal could cause frequency
drift. The global lock also serializes participating writers and should
not be treated as a high-throughput design.

Test the CLI argument and logging contract:

```powershell
poetry run pytest tests/indexer/test_vocabulary_rebuild_cli.py -v
```

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
