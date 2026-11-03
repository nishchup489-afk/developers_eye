---
id: ADR-0014
title: Register sources and enqueue discovery through the same frontier
status: accepted
date: '2026-11-02'
area: crawler
feature: seed-and-discovery
code:
- crawler/src/crawler/seed/seed.py
- crawler/src/crawler/seed/discovery.py
- crawler/src/crawler/seed/registry.py
- crawler/src/crawler/worker/jobs/utility.py
supersedes: null
superseded_by: null
related:
- ADR-0015
- ADR-0018
---

# ADR-0014: Register sources and enqueue discovery through the same frontier

## TL;DR

Treat source configuration as the acquisition contract, then enqueue websites, sitemaps, RSS/Atom, and JSON API targets for the normal crawler. Discovery does not get a second unrestricted fetch path.

## Context

Developer content comes from sites and structured feeds with different resource shapes. Source approval, scheduling, scope, and retries need to remain consistent across them.

## Decision

Source kinds are website, rss, and api; resource target kinds select page/sitemap/rss/api parsing. Seed records insert by slug with ON CONFLICT DO NOTHING; rerunning seed does not apply changed JSON configuration to an existing source. Updating registered source configuration needs an explicit update path. Website discovery reserves the main seed before bounded configured/default sitemap candidates, checks allowlists, and uses enqueue_targets. Robots-advertised sitemaps and structured pagination also re-enter the frontier. JSON source files are runtime inputs; CSV/XLSX are planning inventories, not independent authorities.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Registry plus shared frontier | One scope and retry policy | Configuration must be validated | chosen |
| Network calls inside seed scripts | Short initial script | Bypasses shared scheduling and failure recovery | rejected |
| A worker for every platform | Source-specific tuning | Duplicates lifecycle code before adapters justify it | deferred |

## Why

Reusing the frontier makes discovery replayable and makes a new ingestion format inherit the same operational limits.

## Consequences

- Gained: Bootstrap can be rerun without creating arbitrary duplicate work; it is not a configuration synchronization operation.
- Accepted limitations / tech debt: Generic JSON mapping is not proof that GitHub, Reddit or Stack Overflow authentication/pagination adapters are complete.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Every discovered URL passes frontier and host policy checks.
- A sitemap is discovery data, not a searchable page document.
- New source kinds require schema, seed, parser and worker changes together.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Historical structured-ingestion commits: [87d7e23](https://github.com/nishchup489-afk/developers_eye/commit/87d7e23a65f09edbf64814a450fb458939b4b0e5), [f4478c8](https://github.com/nishchup489-afk/developers_eye/commit/f4478c8591c38f83fc5fc9221882e6490b4316b6), [4e1f581](https://github.com/nishchup489-afk/developers_eye/commit/4e1f58171028cb54332348a9473443fbf8ab910c).

- [`crawler/src/crawler/seed/seed.py`](../../../crawler/src/crawler/seed/seed.py)
- [`crawler/src/crawler/seed/discovery.py`](../../../crawler/src/crawler/seed/discovery.py)
- [`crawler/src/crawler/seed/registry.py`](../../../crawler/src/crawler/seed/registry.py)
- [`crawler/src/crawler/worker/jobs/utility.py`](../../../crawler/src/crawler/worker/jobs/utility.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests`](../../../crawler/tests)
- [`crawler/tests/crawler/parser`](../../../crawler/tests/crawler/parser)

## Revisit when

- A source needs authentication, rate-limit state, or pagination that ApiMapping cannot express.

## Rules for future changes

- Route new discovery paths through enqueue_targets.
- Keep registry behavior separate from future source coverage claims.
