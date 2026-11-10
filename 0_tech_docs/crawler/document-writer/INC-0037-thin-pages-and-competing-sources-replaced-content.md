---
id: INC-0037
title: Thin pages and competing sources replaced richer content and ownership
status: resolved
date: 2026-11-09
severity: medium
area: crawler
feature: document-writer
code: [crawler/src/crawler/writer/documents.py]
fix_commits: []
related: [ADR-0052]
---

# INC-0037: Competing acquisitions lost ownership and richer content

## Signature

A canonical document's source changed after a second website source fetched it;
a short page replaced the full article body previously supplied by a feed.

## Summary

The unconditional page UPSERT erased content and first-source attribution.
Feed-only protections did not cover pages competing with pages or richer feeds.

## Expected vs actual

- Expected: retain acquisition provenance and avoid replacing fuller content with a preview.
- Actual: every successful page fetch replaced source, metadata, and body.

## Root cause

Conflict updates assigned `excluded.source_id` and applied the replacement
predicate only to structured records. Earlier producer metadata was overwritten.

## Resolution

ADR-0052 separates first owner, selected content producer, and per-target
observations. Atomic JSONB merges preserve provenance; a body-length gate
rejects poorer competing content. Finalization records `kept_existing` for
rejected pages as well as feeds/APIs.

## Prevention

- PostgreSQL regressions: `test_competing_sources_preserve_owner_quality_and_observations`
  and `test_thin_page_keeps_full_feed_content_and_its_provenance`.
- Existing rollback, unchanged freshness, tombstone, and feed/page tests remain passing.
- Remaining risk: body length is not semantic quality; complete historical bodies
  are not archived. Legitimate edits by the selected page producer remain allowed.

## Rules for future changes

- Preserve original owner and all latest acquisition observations on conflict.
- Do not advance index freshness for provenance-only sightings.
