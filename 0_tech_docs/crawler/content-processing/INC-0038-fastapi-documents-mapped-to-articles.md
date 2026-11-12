---
id: INC-0038
title: FastAPI documentation fell through to article and event categories
status: resolved
date: 2026-11-09
severity: medium
area: crawler
feature: content-processing
code: [crawler/src/crawler/processing/classifier/classify.py, backend/src/backend/search/categories.py, scripts/backfill_search_categories.py]
fix_commits: []
related: [ADR-0053]
---

# INC-0038: FastAPI documentation mapped to articles

## Signature

Official FastAPI pages classified as `other` appeared under Articles; an events
documentation route appeared under Events instead of Docs.

## Summary

The older audit reported 832 pages. The current corpus contains 140 FastAPI
documents: 63 tutorial, 52 other, 24 documentation, and one event. A dry-run over
100,141 indexes identified 116 derived-category repairs (115 articles→docs,
one events→docs). These are different corpus snapshots, not matching counts.

## Expected vs actual

- Expected: FastAPI's official documentation belongs to the Docs search source.
- Actual: generic title/path heuristics and type fallback mapped many pages elsewhere.

## Root cause

The rules recognized `docs.*` and several documentation domains but not the
dedicated FastAPI documentation host. Tutorial/type fallbacks influenced the UI
category even though the source itself was documentation.

## Resolution

Recognize exactly `fastapi.tiangolo.com` in classification and source mapping.
Provide an offline, bounded, dry-run-first category repair using the same mapper
as indexing. Existing extraction types remain historical; repairing a derived
category does not change document text, vectors, or timestamps.

## Prevention

- PostgreSQL `test_category_backfill_is_previewable_and_idempotent` verifies
  dry-run, apply, and repeated runs.
- Domain matching is exact and must not accept lookalike hosts.
- Concurrent index-category updates are guarded by the previously read value.

## Rules for future changes

- Use one category mapper for index writes, repair, and public results.
- Record the corpus snapshot when investigating historical classification counts.
