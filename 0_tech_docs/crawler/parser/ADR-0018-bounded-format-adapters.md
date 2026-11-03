---
id: ADR-0018
title: Parse HTML, sitemap, feed and JSON resources into explicit shared contracts
status: accepted
date: '2026-11-02'
area: crawler
feature: parser
code:
- crawler/src/crawler/parser/parser.py
- crawler/src/crawler/parser/schemas.py
- crawler/src/crawler/parser/sitemap.py
- crawler/src/crawler/parser/feeds/parser.py
- crawler/src/crawler/parser/api/json_parser.py
supersedes: null
superseded_by: null
related:
- ADR-0014
- ADR-0016
- INC-0012
---

# ADR-0018: Parse HTML, sitemap, feed and JSON resources into explicit shared contracts

## TL;DR

Use bounded format adapters that return documents and discovery links without database writes. Structured resources reuse the crawler pipeline while retaining their own extraction semantics.

## Context

HTML extraction alone misses feeds and API records; treating a sitemap as content pollutes the index. Remote markup and JSON also need finite parsing costs.

## Decision

BeautifulSoup/lxml extracts HTML content, headings, code and links. defusedxml handles XML. Sitemap parsing caps input at 10 MiB and 50,000 entries; feeds and JSON cap input at 2,000,000 bytes and 1,000 entries. These parser caps do not override the lower default fetcher cap. Bounded gzip file MIME handling is allowed specifically for sitemap resources, not as a general binary-fetch exception. JSON mappings select record/field/pagination paths; malformed structures and non-finite numbers are rejected. Robots meta directives are combined, and page policy still applies after parsing.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Shared result contract with format adapters | Reuses safety and storage lifecycle | Adapter edge cases need fixtures | chosen |
| One generic HTML parser for every resource | Fewer modules | Loses sitemap/feed/API semantics | rejected |
| Persist from each parser | Direct implementation path | Duplicates transactions and removal policy | rejected |

## Why

Pure extraction can be tested with fixtures and cannot accidentally bypass the writer or frontier invariants.

## Consequences

- Gained: Formats can evolve without giving them independent persistence authority.
- Accepted limitations / tech debt: Generic mappings are not full vendor integrations; no browser rendering is provided.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Sitemap URLs become discovery links, not content rows.
- Parse results never commit database changes.
- Effective resource size is bounded by every layer it passes through.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Structured edge-case fix: [d9fde47](https://github.com/nishchup489-afk/developers_eye/commit/d9fde47df8dcf18985b4b5c6c0192c2d155f316f).

- [`crawler/src/crawler/parser/parser.py`](../../../crawler/src/crawler/parser/parser.py)
- [`crawler/src/crawler/parser/schemas.py`](../../../crawler/src/crawler/parser/schemas.py)
- [`crawler/src/crawler/parser/sitemap.py`](../../../crawler/src/crawler/parser/sitemap.py)
- [`crawler/src/crawler/parser/feeds/parser.py`](../../../crawler/src/crawler/parser/feeds/parser.py)
- [`crawler/src/crawler/parser/api/json_parser.py`](../../../crawler/src/crawler/parser/api/json_parser.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests/crawler/parser`](../../../crawler/tests/crawler/parser)
- [`crawler/tests`](../../../crawler/tests)

## Revisit when

- A supported source needs a new structure that cannot map without format-specific logic.
- Extraction fixtures show missing main content or code layout.

## Rules for future changes

- Add malformed and boundary fixtures with each adapter change.
- Preserve code indentation and typed discovery links.
