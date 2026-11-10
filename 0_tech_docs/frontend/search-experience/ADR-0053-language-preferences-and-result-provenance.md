---
id: ADR-0053
title: Explicit language preference and transparent result provenance
status: accepted
date: 2026-11-09
area: frontend
feature: search-experience
code: [backend/src/backend/search/presentation.py, backend/src/backend/search/service.py, frontend/components/search, frontend/app/api/search/route.ts]
supersedes:
superseded_by:
related: [ADR-0029, ADR-0031, EXP-0013]
---

# ADR-0053: Language preference and result provenance

## TL;DR

Offer an explicit language preference that stably orders matching-language
candidates first without excluding other languages or changing BM25 scores.
Show declared language, URL-derived documentation version, crawl observation
date, and related variants with their actual scope.

## Context

Translated documentation can share English identifiers while having different
term frequencies and lengths. A high lexical score does not establish the user's
preferred language. Historical diagnostics reported Russian/Portuguese results
above English; the current 100k corpus does not reproduce that ordering for
`FastAPI Depends`, so those historical results are not claimed as a fresh finding.

## Decision

- `language` is an optional validated language tag. With no preference, keep
  score order. With a preference, stable-partition the bounded eligible candidate
  set before pagination; all other languages remain in that set.
- Preserve BM25 scores. This is a user preference, not a tuned ranking weight.
- Use extracted page language or recognized documentation locale paths. Only
  FastAPI's documented unprefixed form implies English. Unknown stays unknown.
- Derive numeric versions only from recognized Python/Django documentation URLs.
- `last_seen_at` means crawler observation, not publication or content revision.
- Related variants are recognized locale/version URL families or exact content
  hashes among retrieved candidates. Counts are not exhaustive corpus totals.
- Page, page size, mode, source, and language travel through shareable result URLs,
  the same-origin proxy, and FastAPI. Page sizes are 1–50 and offset is bounded
  by 1000. There is no invented total; a final full page can lead to an empty next page.
- Load code blocks after pagination, select a bounded relevant excerpt, and render
  code and highlights as escaped React text. No provider HTML is trusted.

## Options considered

| Option | Benefit | Cost | Verdict |
| --- | --- | --- | --- |
| Explicit stable language preference | Predictable, reversible, preserves translations | Candidate-window scope | Chosen |
| Remove all non-English content | Simple | Permanently hides useful results | Rejected |
| Tune language weights silently | Can blend signals | Unexplained scoring changes before judged evaluation | Rejected |
| Hide all duplicate variants | Fewer rows | Could erase a requested version/translation | Rejected; distinguish them |

## Why

The metadata describes what was observed. It does not guess publication dates,
claim language detection, or infer arbitrary cross-site equivalence.

## Consequences

Preference ordering is stable within the current candidate snapshot; live corpus
changes can still move results between requests. Bookmarks remain browser-local.
Version families are deliberately conservative and may miss unknown layouts.

## Invariants

- Preferred-language and unpreferred searches have the same eligible candidates and scores.
- Version/translation URLs remain clickable and are not collapsed away.
- Metadata is validated at the frontend boundary and rendered as plain text.
- All options survive refresh; source/mode/preference changes reset to page one.

## Evidence

47 targeted backend tests and frontend search-unit, lint, typecheck, production
build, and HTTP integration checks passed during implementation. PostgreSQL tests
cover preserved translations/scores, freshness, variant recognition, and idempotent
category repair. The raw local comparison is in
`backend/reports/checklist/language-preference.json`.

## Revisit when

A judged dataset demonstrates a better preference policy, or complete corpus-wide
variant grouping is required. Measure recall before changing candidate budgets.

## Rules for future changes

- Never describe declared language as verified language detection.
- Keep explicit preference separate from lexical scoring and source filtering.
- Preserve source URLs, observation semantics, and bounded paging.
