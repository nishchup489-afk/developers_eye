---
id: ADR-0013
title: Separate acquisition, indexing, and query serving around PostgreSQL
status: accepted
date: '2026-11-02'
area: infra
feature: system-architecture
code:
- backend/src/backend/main.py
- crawler/src/crawler/worker/runner.py
- crawler/src/indexer/worker/runner.py
- frontend/app/api/search/route.ts
supersedes: null
superseded_by: null
related:
- ADR-0004
- ADR-0008
- ADR-0010
- ADR-0012
---

# ADR-0013: Separate acquisition, indexing, and query serving around PostgreSQL

## TL;DR

Run the API, crawler, indexer, and Next.js application as separate processes with one durable PostgreSQL model. Slow upstream acquisition stays outside the user search request.

## Context

The original design included a custom inverted index, Redis/ARQ, and more workers. The implementation instead reuses PostgreSQL for frontier state, documents, vectors, and reporting. The project needs an understandable working search engine before extra infrastructure.

## Decision

Backend owns schema and public/admin APIs; crawler and indexer import that package through the relative dependency. Next.js proxies HTTP to FastAPI. The crawler writes documents; the indexer reads freshness and writes search_index. The current public service reads the stored index. Redis is a declared dependency, but no running Redis queue or cache is established by this snapshot. Nginx, a custom inverted index, Kubernetes, semantic retrieval and RAG remain future directions.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Four processes, shared PostgreSQL | Independent lifecycles and durable state | Shared database contention | chosen |
| Live fan-out to every upstream per search | Fresh upstream answers | User latency and availability inherit each upstream | deferred |
| Broker and separate search engine immediately | More independent scaling knobs | Extra delivery, repair and operational contracts | deferred until measured need |

## Why

Network-bound work and query latency have different failure and scheduling needs. A shared database avoids a second consistency protocol while preserving clear module ownership.

## Consequences

- Gained: Durable acquisition and incremental indexing can continue independently of UI requests.
- Accepted limitations / tech debt: The database is a shared bottleneck; process separation does not prove distributed readiness or high QPS.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Serving a stored-index query does not trigger a crawl.
- Backend imports neither crawler nor indexer.
- A dependency declaration is not evidence of a deployed service.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/src/backend/main.py`](../../../backend/src/backend/main.py)
- [`crawler/src/crawler/worker/runner.py`](../../../crawler/src/crawler/worker/runner.py)
- [`crawler/src/indexer/worker/runner.py`](../../../crawler/src/indexer/worker/runner.py)
- [`frontend/app/api/search/route.ts`](../../../frontend/app/api/search/route.ts)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/tests/test_package_boundary.py`](../../../backend/tests/test_package_boundary.py)
- [`crawler/tests/crawler/worker`](../../../crawler/tests/crawler/worker)
- [`crawler/tests/indexer`](../../../crawler/tests/indexer)

## Revisit when

- Database contention remains dominant after profiling and query/index improvements.
- A second crawler process must share host rate limits.

## Rules for future changes

- Keep acquisition and indexing outside the search request.
- Update the architecture status table before claiming a planned component is live.
