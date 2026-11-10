# Document persistence and availability

Area: crawler · Status: active

## Purpose

Persists extracted content and durable attempts. Unavailable pages retain document identity; index removal must coordinate vocabulary deltas. Raw response HTML is not an archive in this design.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/writer`](../../../crawler/src/crawler/writer)
- [`crawler/src/crawler/worker/jobs/utility.py`](../../../crawler/src/crawler/worker/jobs/utility.py)

## How-it-works docs

- [`crawler/src/crawler/writer/docs/developers_eye_writer_docs.md`](../../../crawler/src/crawler/writer/docs/developers_eye_writer_docs.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0011](ADR-0011-soft-availability-for-removed-pages.md) | decision | A 404 or 410 marks stored documents unavailable instead of deleting them, and they can come back | accepted |
| [ADR-0021](ADR-0021-extracted-content-and-writer-ownership.md) | decision | Persist extracted documents rather than raw HTML in the primary store | accepted |
| [ADR-0036](../../indexer/vocubulary/ADR-0036-vocabulary-maintenance-and-lock-boundary.md) | decision | Keep vocabulary maintenance transactional and rebuild it with a one-shot CLI | accepted |
| [ADR-0050](ADR-0050-feed-records-never-replace-fetched-pages.md) | decision | A feed or API record never replaces a fetched page, and only a page can remove or revive one | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Preserve first acquisition ownership and per-target provenance; use ADR-0052
  for current producer/quality rules (supersedes ADR-0050).

- Never hard-delete a document because of a 404/410; mark it unavailable (ADR-0011).
- Remove index rows in the same transaction through `remove_indexed_documents()` (ADR-0011, ADR-0002).
- Every successful page store resets `is_available`, `unavailable_at`, `unavailable_http_status` (ADR-0011). A feed or API record never does (ADR-0050).
- A feed or API record must not replace a fetched page (ADR-0050).
- Do not add raw-body persistence without retention, size and replay contracts.
- Keep removal and revival semantics covered by persistence tests.
- Fix incremental correctness before recounting and resuming writers.
- Do not reintroduce a permanent vocabulary worker without an ADR.
- Measure contention before replacing the mutex.
