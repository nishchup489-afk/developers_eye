---
id: ADR-0052
title: Preserve first acquisition ownership and reject poorer replacement content
status: accepted
date: 2026-11-09
area: crawler
feature: document-writer
code: [crawler/src/crawler/writer/documents.py, crawler/src/crawler/worker/jobs/utility.py]
supersedes: ADR-0050
superseded_by:
related: [ADR-0011, ADR-0021, INC-0037]
---

# ADR-0052: Acquisition provenance and content quality

## TL;DR

Keep `document.source_id` as the first acquisition owner. Record the selected
content producer and each acquisition target's latest observation separately in
JSONB. A different producer or a page replacing a feed must supply at least as
much body text; an existing page producer may make shorter legitimate edits.

## Context

ADR-0050 prevented feeds from overwriting fetched pages, but two website sources
still replaced ownership and a thin page could erase a fuller feed article.
Canonical URL identity stays global; multiple observations need provenance.

## Decision

- Preserve the first `source_id` on conflict; `metadata.content_source_id` identifies
  the selected content producer.
- Atomically merge `metadata.acquisition_provenance`, keyed by source/target ID.
  Each value contains source, target, origin URL, ingestion format, content hash,
  and body character count. It is latest-observation provenance, not an attempt log.
- Lazily capture a legacy row's existing owner/origin before its first merge.
- Keep the feed/API protection and removed-page rules from ADR-0050. A page
  replacing structured content, or a competing page producer, must not shorten
  the stored body. The selected page producer may edit its own page.
- Sighting/provenance-only updates do not change `updated_at`; selected content
  and index-relevant metadata changes do. Keep all writes in the caller's transaction.
- `store_document` returns the atomic selection decision with the ID; finalization
  does not issue another SELECT to infer whether content was kept. `upsert_document`
  retains the existing ID-only API for other callers.

## Options considered

| Option | Benefit | Cost | Verdict |
| --- | --- | --- | --- |
| Atomic per-target JSONB provenance | No new table or migration; retains competing observations | Metadata grows with distinct producers/targets | Chosen |
| Separate acquisition history table | Complete event history and independent retention | More tables/writes; attempts already hold fetch history | Deferred |
| Latest writer owns the row | Simple | Loses ownership and richer content | Rejected |

## Why

The existing canonical identity and JSONB store can retain the small set of
competing producers without moving network work into transactions. A body-length
gate prevents the reproduced loss; it is a conservative proxy, not a semantic
quality score. Current producers can still publish corrections and deletions.

## Consequences

Operational source attribution means first acquisition; the content producer is
explicitly separate. Provenance is not historical content archival. Existing rows
gain provenance lazily and their earlier unseen acquisitions cannot be recovered.

## Invariants

- Competing sources do not change the original `source_id`.
- Rejected content still contributes an observation and never revives a removed page.
- An unchanged sighting does not trigger reindexing.
- Provenance and content roll back with the worker transaction.

## Evidence

The writer, pipeline, and monitoring suites passed 44 tests, including competing
page sources, page/feed quality, unchanged sightings, rollback, tombstones,
nested sitemap scoping, and partial-commit replay.

## Revisit when

Distinct acquisitions materially increase document size, or independent producer
history/retention becomes necessary. Measure metadata sizes before normalizing it.

## Rules for future changes

- Keep original ownership distinct from selected content ownership.
- Preserve existing provenance on every accepted and rejected acquisition.
- Keep quality, removal/revival, freshness, and rollback persistence tests passing.
