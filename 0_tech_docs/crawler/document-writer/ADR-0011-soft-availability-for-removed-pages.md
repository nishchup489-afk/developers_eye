---
id: ADR-0011
title: A 404 or 410 marks stored documents unavailable instead of deleting them, and they can come back
status: accepted
date: 2026-10-20
area: crawler
feature: document-writer
code:
  - crawler/src/crawler/worker/jobs/utility.py:_finalize
  - crawler/src/crawler/worker/jobs/jobs.py:process_job
  - crawler/src/crawler/writer/documents.py
  - backend/src/backend/models/documents.py
  - backend/alembic/versions/e94b530df145_document_availability.py
  - crawler/src/indexer/selector.py:select_removal_candidates
supersedes:
superseded_by:
related: [ADR-0002, ADR-0008]
---

# ADR-0011: Soft availability for removed pages

## TL;DR
When a page the crawler has stored returns HTTP 404 or 410, its `document` rows are kept but marked `is_available = false` with `unavailable_at` and `unavailable_http_status`, and their `search_index` rows are removed in the same transaction. The target stays scheduled and is checked again after the normal recrawl interval. If a later fetch succeeds, the writer clears the three fields and the page is indexed again. Search never shows a dead page, and nothing is lost if the 404 was temporary.

## Context
Before commit `9a29b29` (2026-10-20), a 404/410 permanently disabled the crawl target, and the stored document stayed exactly as it was: still `document` content, still in `search_index`, indistinguishable from a live page, and never checked again (`0_tech_docs/journal/update-log/09_content_availability.md`). So search could return pages that no longer existed, forever.

Websites return 404 for reasons that are not permanent: a deploy in progress, a moved docs version, a CDN glitch. Deleting the document on the first 404 would throw away content that might be back an hour later.

> **Question for nish:** did you consider deleting on 410 (which means "gone on purpose") and only soft-marking on 404? The code treats them the same. If that was deliberate, say why.

## Decision
- **On 404/410** (`process_job` → action `complete`, outcome `failed`; then `_finalize`):
  - `UPDATE document SET is_available = false, unavailable_http_status = <status>, unavailable_at = COALESCE(unavailable_at, clock_timestamp()) WHERE last_crawl_target_id = <target>`, returning the ids;
  - `remove_indexed_documents(session, ids)` deletes their `search_index` rows and decrements vocabulary counts (ADR-0002), in the same transaction;
  - the target is completed normally (`complete_target`), so it is fetched again after `crawl_interval_seconds`.
- **Body is kept** so the admin inspector can show what the page was and when and why it went away.
- **Recovery.** A later successful store (`writer/documents.py`) sets `is_available = true`, `unavailable_at = NULL`, `unavailable_http_status = NULL`. That updates `document.updated_at`, so the indexer picks it up again (ADR-0008).
- **Indexer side.** `select_index_candidates` skips unavailable documents; `select_removal_candidates` also finds unavailable documents that still have an index row, as a safety net.
- **Migration** `e94b530df145` added the three columns and marked historical documents whose latest finished attempt was 404/410, without touching manually disabled targets.
- `noindex` is different: those documents are deleted, not soft-marked (see `_finalize`).

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Soft-mark unavailable, drop from index, keep checking, restore on success | Search stays correct; temporary 404s recover; history visible in admin | Dead content stays in the table; recheck traffic to dead URLs forever | chosen |
| B. Disable the target and leave the document (the old behaviour) | Nothing to build | Dead pages stay searchable and are never rechecked | rejected: the bug |
| C. Hard-delete the document on 404/410 | Table stays small | A temporary 404 loses content; cascades skip vocabulary decrements | rejected |
| D. Soft-mark, but delete after N days unavailable | Bounded storage | Needs a cleanup job and a retention rule | not done yet |

## Why
- **Correctness of results.** The index row is removed in the same transaction as the 404 is recorded, so there is no window where search shows a page we know is gone.
- **Reliability.** A one-off 404 costs one recrawl interval of absence, not the page.
- **Operability.** The admin inspector shows the status and timestamp, so "why did this page disappear from search" has an answer.

## Consequences
- Gained: correct search results for removed pages and automatic recovery.
- Accepted limitations:
  - Unavailable documents are kept forever (no retention).
  - Dead URLs keep being fetched every `crawl_interval_seconds`, with no extra backoff (a 404 is a `complete`, not a failure, so ADR-0006 does not apply).
  - The update matches documents by `last_crawl_target_id`; a document last written by another target (a feed entry, for example) is not marked when its own page 404s.
- What depends on this: the indexer's freshness rules (ADR-0008), vocabulary counts (ADR-0002), admin reporting (pending-index counts exclude unavailable documents).

## Invariants
- `is_available = false` implies no `search_index` row for that document after the transaction commits.
- `unavailable_at` keeps the first time the page went away (`COALESCE`), not the latest.
- A successful store always resets all three availability fields.
- The index removal goes through `remove_indexed_documents()`, never a bare `DELETE` on `search_index`.

## Evidence
- Tests: 404 and 410 finalization, search invalidation, kept document rows and restoration (`crawler/src/crawler/worker/tests/test_postgres_pipeline.py::test_removed_page_invalidates_index_and_recovers_when_restored`), `indexer/tests/test_indexer.py` steps 8 and 9 (soft-unavailable removal, revived document).
- Measured: none.
- Commits: `9a29b29`, `4043255` (Postgres coverage), `c0d1690` (vocabulary-aware removal).

## Revisit when
- Unavailable documents become a large share of the `document` table; add retention (option D).
- Recrawling dead URLs is a noticeable share of fetches; add a longer interval or backoff for targets whose last result was 404/410.
- Feed or API documents need to be marked unavailable when their canonical page 404s.

## Rules for future changes
- Never hard-delete a document because of a 404/410; mark it unavailable.
- Remove index rows in the same transaction that marks the document unavailable, through `remove_indexed_documents()`.
- Any path that stores a document successfully must reset `is_available`, `unavailable_at` and `unavailable_http_status`.
- Keep passing: `worker/tests/test_postgres_pipeline.py`, `indexer/tests/test_indexer.py`.
