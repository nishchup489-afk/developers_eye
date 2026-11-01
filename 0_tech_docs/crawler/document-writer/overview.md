# Document and attempt writer

Area: crawler · Status: active

## Purpose
Persists extracted documents and crawl attempts: upserts `document` rows by canonical URL and content hash, records each attempt's outcome and telemetry, and keeps document availability in step with what the site returns. It does not store raw HTML and does not write the search index (the indexer does).

## Code
- `crawler/src/crawler/writer/`

## How-it-works docs
- `crawler/src/crawler/writer/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0011](ADR-0011-soft-availability-for-removed-pages.md) | decision | Soft availability for removed pages | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Raw HTML is not stored
- [x] Soft availability: 404/410 marks a document unavailable instead of deleting it (ADR-0011)

## Rules for future changes
- Never hard-delete a document because of a 404/410; mark it unavailable (ADR-0011).
- Remove index rows in the same transaction through `remove_indexed_documents()` (ADR-0011, ADR-0002).
- Every successful store resets `is_available`, `unavailable_at`, `unavailable_http_status` (ADR-0011).
