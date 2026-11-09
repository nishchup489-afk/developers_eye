---
id: ADR-0050
title: A feed or API record never replaces a fetched page, and only a page can remove or revive one
status: accepted
date: 2026-11-09
area: crawler
feature: document-writer
code:
  - crawler/src/crawler/writer/documents.py:upsert_document
  - crawler/src/crawler/worker/jobs/utility.py:_finalize
  - crawler/src/crawler/worker/jobs/utility.py:_noindex_urls
supersedes:
superseded_by:
related: [ADR-0011, ADR-0021]
---

# ADR-0050: Feed and API records do not own fetched pages

## TL;DR
One `document` row exists per canonical URL, and feeds and APIs write to the same URL as the article they describe. A page fetch always takes the row. A feed or API record can only replace another feed or API record, never a fetched page and never a removed document. When it may not replace the row it counts as a sighting and changes nothing else.

## Context
`upsert_document` overwrote every column on conflict, so the last writer won. Found while reading the write path before a 20-worker crawl:

- A feed entry replaced the full article body with its summary, and changed `content_hash`, so the indexer rebuilt the row with less text.
- The same write moved `source_id` and `last_crawl_target_id` to the feed. A 404 on the feed URL then marked every article it had last written as unavailable, and a 404 on the article itself matched nothing.
- `is_available` was reset on every store, so a stale feed entry brought back a page that had gone 404 or noindex.
- An `X-Robots-Tag: noindex` on a feed response marked the articles its entries point to as unavailable. WordPress sends that header on every feed.

The next crawl starts from an empty database, so no stored rows need repair.

## Decision
- Rows are told apart by `metadata.ingestion_format`: `rss`, `atom` or `json_api` mean structured, anything else means the page was fetched.
- **A page fetch** behaves as before and always takes the row, including replacing an earlier feed summary.
- **A structured record** replaces the row only when the row is available, was itself written by a structured record, and either came from the same feed or API, or holds no more text than the incoming record.
- The rule is the `WHERE` of the `ON CONFLICT DO UPDATE`, so it is decided atomically by PostgreSQL. A kept row refreshes only `last_seen_at`, and not even that if the row is removed. `updated_at` stays, so the indexer has nothing to do.
- A kept record is logged with decision `kept_existing` and counted as skipped, not stored.
- **A 404 or 410** marks the row at the target's own URL, plus rows this target last wrote from a page fetch. A missing feed removes nothing but itself.
- **noindex on a feed or API response** still stops its records being stored, but no longer marks the pages they point to.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Keep whichever body is longest, from any source | One simple rule | A page that really got shorter could never shrink, and a long feed copy would beat the canonical page | rejected |
| Add a `content_origin` column | Queryable without JSONB | Needs a migration for a value the metadata already holds | rejected for now |
| Rule in `ON CONFLICT ... WHERE`, using existing metadata | Atomic, no migration, page path unchanged | Depends on `ingestion_format` staying accurate | chosen |
| Stop storing feed entries when a page target exists | Removes the conflict | Loses content for sites whose article pages cannot be fetched | rejected |

## Why
The page at the canonical URL is the thing a search result links to, so its text is the record of truth. Feeds are useful for discovery and as a fallback when no page was fetched, which is what this rule keeps.

## Consequences
- Feed content for an article that was already fetched is dropped even when the feed happens to be longer.
- A thin page fetch still replaces a full feed entry. That is the old behaviour and is not addressed here.
- Two website sources that crawl the same canonical URL are still last-writer-wins for `source_id`.
- The same feed may still shorten its own entry, so a legitimate edit is not frozen.

## Invariants
- A structured record never changes the content, owner or availability of a page-fetched row.
- A structured record never makes an unavailable row available.
- A 404 or 410 on a feed or API target never marks an article unavailable.

## Evidence
`crawler/tests/crawler/worker/test_postgres_pipeline.py` runs each case through `process_job` on PostgreSQL. Eight of those cases fail on the previous code and pass now. `crawler/tests/indexer/test_index_lifecycle.py` covers unchanged, updated, removed and rebuilt documents.

## Revisit when
- A source needs its feed to win over its pages, for example pages that are only a JavaScript shell.
- Overlapping website sources appear and need an explicit ownership rule.

## Rules for future changes
- Any new parser that writes records describing another URL must set `ingestion_format` and be added to `STRUCTURED_FORMATS`.
- Do not write document columns from a structured record outside `upsert_document`.
