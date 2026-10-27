# `reporting.py` — indexer coverage report

## Responsibility

Read-only SQLAlchemy queries measure **coverage**, not historic throughput:

- Count all and available `document` records.
- Split available documents into **current**, **missing**, and **stale**.
- Count all `search_index` records, including old/soft-unavailable ones.
- Find the most recent completed indexing timestamp.

`current` matches the selector's freshness contract: `indexed_at >=
document.updated_at` and `indexed_hash` starts with `v{INDEXER_INDEX_VERSION}:`.
`pending = missing + stale`.

## API

`coverage_statement(config)` returns a SQLAlchemy `Select` for aggregate coverage.
`get_indexer_report(session, config=config)` returns an immutable `IndexerReport`.
`IndexerReport.to_dict()` gives JSON-ready values with ISO timestamps.

## CLI

```powershell
poetry run python -m indexer.reporting
```

Example *illustrative* output:

```json
{
  "available_documents": 100,
  "current_documents": 75,
  "missing_documents": 20,
  "stale_documents": 5,
  "pending_documents": 25,
  "index_version": 2,
  "indexed_rows": 80,
  "unavailable_index_rows": 0,
  "total_documents": 100,
  "generated_at": "2026-10-27T08:00:00+00:00",
  "last_indexed_at": "2026-10-27T07:55:00+00:00"
}
```

Note: those numbers and timestamps are mock examples, not project measurements.

## Limits

Two SQL queries are executed in one read session, without a snapshot-level
transaction guarantee under PostgreSQL's default READ COMMITTED isolation.
The output can briefly shift during active indexing.

The module cannot report failed attempts, retry count, indexing speed, or p95
latency without persisted event history or logs. It does not add a FastAPI
endpoint; integrate the function with your existing admin router separately.
