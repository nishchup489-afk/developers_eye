---
id: ADR-0015
title: Normalize URL identity conservatively and enforce crawl scope at insertion
status: accepted
date: '2026-11-02'
area: crawler
feature: url-frontier
code:
- crawler/src/crawler/frontier/urls.py
- crawler/src/crawler/frontier/repository.py
- crawler/src/crawler/frontier/scope.py
- backend/src/backend/models/crawler_frontier.py
supersedes: null
superseded_by: null
related:
- INC-0002
- INC-0003
---

# ADR-0015: Normalize URL identity conservatively and enforce crawl scope at insertion

## TL;DR

Deduplicate by source_id and normalized_url and enforce depth, path and page limits where targets are inserted. Preserve path and query semantics rather than guessing equivalence.

## Context

Duplicate URLs waste crawl capacity; aggressive canonicalization can merge distinct developer pages. Earlier scope settings existed without enforcement, recorded in INC-0003.

## Decision

Normalize scheme/host, IDNA/IP spelling, default ports, empty path and fragments; preserve path and query ordering. Reject credentials, malformed escapes and unsupported schemes. Enqueue deduplicated rows in deterministic order. Scope defaults are depth 3 and 10,000 pages; source configuration can narrow allowed path prefixes. A per-source advisory lock protects count-then-insert budget enforcement. These locks are distinct from scheduler source-row locks and the vocabulary mutex.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Conservative normalization and database uniqueness | Predictable identity | Some semantically duplicate URLs remain | chosen |
| Strip all query strings or lowercase paths | More apparent deduplication | Can merge versions, languages and case-sensitive routes | rejected |
| Check budgets only in discovery | Cheap helper code | Other insertion paths bypass limits | rejected |

## Why

Correct URL identity and one authoritative insertion boundary matter more than maximizing a deduplication ratio.

## Consequences

- Gained: Bounded scope holds across competing insertion paths.
- Accepted limitations / tech debt: Source budgets count frontier resources, not just useful documents; future budget changes require a migration/behavior review.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- (source_id, normalized_url) stays unique.
- Budget checks and inserts share their protecting transaction.
- Batch insertion ordering is deterministic.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`crawler/src/crawler/frontier/urls.py`](../../../crawler/src/crawler/frontier/urls.py)
- [`crawler/src/crawler/frontier/repository.py`](../../../crawler/src/crawler/frontier/repository.py)
- [`crawler/src/crawler/frontier/scope.py`](../../../crawler/src/crawler/frontier/scope.py)
- [`backend/src/backend/models/crawler_frontier.py`](../../../backend/src/backend/models/crawler_frontier.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/src/crawler/frontier/tests`](../../../crawler/src/crawler/frontier/tests)
- [`crawler/src/crawler/frontier/tests`](../../../crawler/src/crawler/frontier/tests)

## Revisit when

- Equivalent tracking URLs measurably dominate the frontier, with source-specific evidence.
- Budget lock waits dominate acquisition throughput.

## Rules for future changes

- Do not strip query parameters globally.
- Keep all enqueue paths behind scope checks and deterministic lock ordering.
