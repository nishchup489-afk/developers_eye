---
id: ADR-0029
title: Generate bounded plain-text passages with separate highlight offsets
status: accepted
date: '2026-11-02'
area: backend
feature: snippets
code:
- backend/src/backend/search/snippets/snippets.py
- backend/src/backend/search/snippets/ranking.py
- backend/src/backend/search/snippets/validation.py
- backend/src/backend/search/snippets/types.py
supersedes: null
superseded_by: null
related:
- INC-0009
- ADR-0028
---

# ADR-0029: Generate bounded plain-text passages with separate highlight offsets

## TL;DR

The snippet component selects query-relevant excerpts and returns plain text plus character spans. It is independent of database access and final document ranking; the public service still uses ts_headline.

## Context

A useful result should show why it matches without trusting crawled HTML. Repeated terms near the beginning of a page should not consume all excerpt candidates.

## Decision

Normalize prose or preserve code layout, cap query terms at 32 and term length at 128, escape matching patterns, and sample matches across eight regions per term. Deduplicate windows; score 4 points per distinct term plus up to 3 occurrences per term; earlier windows break ties. Candidate output defaults to 64 and snippets to 200 characters. The matcher still scans the input text; candidate caps are not a full input-size limit. Missing matches fall back to description then document prefix. Offsets are end-exclusive in final Snippet.text; truncation is metadata. INC-0009 records the boundary-budget fix.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Plain text with spans | Safe rendering boundary, reusable tests | Caller must map Unicode offsets correctly | chosen |
| Return highlighted HTML | Easy initial markup | Adds sanitization/trust risks | rejected |
| Always take document prefix | Cheap | Misses relevant later content | rejected |

## Why

Content selection belongs in the backend component; HTML rendering belongs to the UI. Capping repetition rewards coverage over keyword stuffing.

## Consequences

- Gained: Deterministic excerpts, code-aware windows and explicit truncation.
- Accepted limitations / tech debt: Python offsets count Unicode code points while JavaScript string indices use UTF-16 units. A future spans API needs conversion/contract tests, especially for emoji. Regex matching is not PostgreSQL stemming.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- len(snippet.text)<=max_chars after all boundary adjustments.
- Spans refer to the returned text and do not overlap.
- Snippet passage scores do not reorder documents.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. PR [#6](https://github.com/nishchup489-afk/developers_eye/pull/6) fixed the length regression in [d2229b6](https://github.com/nishchup489-afk/developers_eye/commit/d2229b6ffb8a7f9aff270889f40ebcd115069723).

- [`backend/src/backend/search/snippets/snippets.py`](../../../backend/src/backend/search/snippets/snippets.py)
- [`backend/src/backend/search/snippets/ranking.py`](../../../backend/src/backend/search/snippets/ranking.py)
- [`backend/src/backend/search/snippets/validation.py`](../../../backend/src/backend/search/snippets/validation.py)
- [`backend/src/backend/search/snippets/types.py`](../../../backend/src/backend/search/snippets/types.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/tests/unit/test_snippets.py`](../../../backend/tests/unit/test_snippets.py)
- [`backend/tests/unit/test_snippet_bounds.py`](../../../backend/tests/unit/test_snippet_bounds.py)

## Revisit when

- Before replacing ts_headline or exposing spans to the frontend.
- Full-document scan cost becomes material after profiling top-result snippets.

## Rules for future changes

- Render snippet content as text, not trusted HTML.
- Generate snippets after final top-result selection.
- Preserve the hard character cap when improving word/line boundaries.
