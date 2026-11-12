---
id: INC-0043
title: Slow searches tab rejected an empty window as invalid data
status: resolved
date: 2026-11-12
severity: low
area: frontend
feature: admin-console
code: [frontend/lib/search-quality.ts:isSlowSearchReport, backend/src/backend/admin_services/search_quality.py:build_slow_query_report]
fix_commits: [d5a02a7]
related: [ADR-0057]
---

# INC-0043: Slow searches tab rejected an empty window as invalid data

## Signature
```
Slow searches are unavailable
The crawler service returned invalid monitoring data.
```

## Summary
Right after `alembic upgrade head`, the admin Search quality page's Slow searches tab showed "invalid
monitoring data" instead of an empty list. Nothing was lost; the tab was unusable until a slow search was
recorded.

## Expected vs actual
- Expected: an empty window shows zero slow searches and "N/A" stage means.
- Actual: the Next.js proxy rejected the backend's response with a 502.

## Root cause
`build_slow_query_report` sends `null` as the mean of a stage with no timings, which is every stage when
the window has no slow searches. `isSlowSearchReport` checked `stage_means_ms` with a numbers-only map, and
its unit test even asserted that a null mean is invalid, so the backend and frontend contracts disagreed.
Verification during ADR-0057 used a database that already had slow searches, so every mean was a number.

## Resolution
`stage_means_ms` is typed `number | null` per stage and validated as nullable; the page already showed
`N/A` for null. The unit test now accepts an empty window with all-null means and still rejects a string.

## Prevention
- Regression test: `frontend/tests/search-quality-unit.mjs` (empty window case).
- Remaining risk: fixtures are written by hand; a contract test that feeds a real empty backend report to
  the validator would catch the next mismatch.

## Rules for future changes
- When a backend report can return `null`, test the frontend validator with the empty case, not only a populated fixture.
