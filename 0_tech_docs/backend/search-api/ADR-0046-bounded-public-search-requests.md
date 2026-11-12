---
id: ADR-0046
title: Bound every public search with a rate limit, a concurrency cap, deadlines and cancellation
status: accepted
date: 2026-11-08
area: backend
feature: search-api
code:
  - backend/src/backend/api/search.py
  - backend/src/backend/api/request_limits.py
  - frontend/app/api/search/route.ts
  - frontend/app/api/search/suggest/route.ts
  - frontend/lib/search.ts
  - deploy/docker-compose.yml
supersedes:
superseded_by:
related: [ADR-0003, ADR-0044, INC-0033, EXP-0008]
---

# ADR-0046: Bound every public search with a rate limit, a concurrency cap, deadlines and cancellation

## TL;DR
`/search` and `/search/suggest` now reject a client over its rate with 429, reject work over the concurrency cap with 503, and stop any request after a deadline with 504. A browser that goes away cancels its query in PostgreSQL. These are all in-process, because one server with two API workers does not justify a shared limiter yet.

## Context
A search can take seconds on cold common terms (EXP-0008), and each one holds a pooled connection. Before this change there was no rate limit and no total deadline. A statement timeout came back as 503, abandoned searches kept running, and the proxy accepted 300 characters while the analyzer accepted 256.

The API runs behind Next.js and Caddy on one server, with two uvicorn workers and a pool of 8 + 2 connections per worker.

## Decision
A request meets these in order:

1. **Rate limit.** A token bucket per client, in `RateLimiter`. Default 60 per minute with a burst of 20 (`SEARCH_RATE_LIMIT_PER_MINUTE`, `SEARCH_RATE_LIMIT_BURST`; 0 per minute disables it). Over the limit is 429 with `Retry-After`. Searches and suggestions have separate buckets, because one results page makes one of each. At most 10,000 clients are remembered.
2. **Validation.** 422 from FastAPI. See "Query length" below.
3. **Concurrency cap.** `SEARCH_MAX_CONCURRENT` (16) slots per process, shared by searches and suggestions because they share the pool. A slot is taken without queueing; no free slot is 503 with `Retry-After: 1`.
4. **Deadlines.** `statement_timeout` of `SEARCH_QUERY_DEADLINE_MS` (3 s) per statement, and `asyncio.timeout` of `SEARCH_TOTAL_DEADLINE_MS` (4 s) around the whole request, including the wait for a connection. Either one, or a connection pool timeout, is 504.
5. **Disconnects.** `run_unless_disconnected` races the search against `http.disconnect`. A disconnect cancels the search, and the cancel reaches PostgreSQL through asyncpg. The search always finishes unwinding before the slot is released.

The Next.js proxy forwards the last `X-Forwarded-For` entry, passes `request.signal` to the upstream call, and keeps 429, 503 and 504 with their `Retry-After`. Its timeouts (6 s for search, 5 s for suggestions) sit above FastAPI's 4 s, so a slow search is reported by FastAPI.

The client address comes from uvicorn's proxy header handling. Compose sets `FORWARDED_ALLOW_IPS=*` on the API service, which is safe only because its port is published to nothing but the web container.

### Query length
FastAPI counts NFC code points after collapsing whitespace outside double quotes, up to 256, and refuses more than 1024 raw characters first. `normalizedQueryLength` in `frontend/lib/search.ts` counts the same way, so the proxy and FastAPI accept the same queries. A backend test fails if the two sets of constants drift.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. In-process token buckets and a semaphore | No new service, no added latency, no write per search | Each worker keeps its own buckets, so the real rate is up to workers x limit | chosen |
| B. Limits in PostgreSQL | One shared count | Adds a write to every search, and the database is what we are protecting | rejected: wrong place for the load |
| C. Redis | Accurate and fast | A new service on a single free-tier server | rejected for now |
| D. Limit in Caddy | Stops traffic earliest | Needs a third-party Caddy build, and cannot see overload inside the API | rejected for now |
| E. Queue requests over the cap | Fewer failures in a burst | Queued requests spend their deadline waiting and return 504 anyway | rejected: fail fast with 503 |

## Why
The limits exist to protect one connection pool on one server, so the check should cost nothing and live next to the pool. Two workers doubling the limit is a small error compared with having no limit. Failing early with `Retry-After` tells the browser something true, where a long wait followed by a timeout does not.

## Consequences
- Gained: a bounded search cost, distinct errors for "slow down", "busy" and "timed out", and no work for clients that left.
- Accepted limitations: limits are per process and reset on restart. Under a heavy burst, suggestions and searches compete for the same slots. `/api/search/knowledge` is not rate limited; it is bounded by its cache and a 4 s timeout, and it is not cancelled by the browser because concurrent callers share one upstream request.
- What now depends on this: production needs `FORWARDED_ALLOW_IPS`, or every visitor shares one bucket.

## Invariants
- `SEARCH_QUERY_DEADLINE_MS` < `SEARCH_TOTAL_DEADLINE_MS` < the Next.js proxy timeout.
- The FastAPI port is never published directly while `FORWARDED_ALLOW_IPS=*` is set.
- A slot is released on every path, and only after the search has unwound.
- The check and the take of a slot have no `await` that can yield between them.
- `maxQueryLength` and `maxRawQueryLength` equal the `SearchConfig` defaults.

## Failure modes
- **Forwarded header not trusted:** all visitors share one bucket and get 429 early. The E2E test covers per-visitor buckets locally; check it after any proxy change.
- **Cold common-term search:** can still hit the 3 s statement timeout and return 504 (EXP-0008). The deadline bounds the cost; it does not make the query fast.
- **Client disconnects after the search finished:** the response is dropped and the search counts as successful.

## Evidence
- Measured: no latency numbers were taken for this change.
- Assumed: 60 per minute with a burst of 20 suits a person searching by hand.
- Tests: `backend/tests/api/test_search_limits.py`, `backend/tests/integration/test_search_deadlines.py`, `frontend/tests/integration.mjs`, `frontend/tests/search-unit.mjs`, and `scripts/e2e_search_stack.py`, which runs real Next.js and FastAPI against a fresh PostgreSQL database and uses a held table lock to make queries really slow.

## Revisit when
- The API runs on more than one host, or more than 4 workers per host.
- 429s appear for real users in the admin search report.
- More than 1% of searches return 503 or 504 over a day.

## Rules for future changes
- Do not publish the API port without narrowing `FORWARDED_ALLOW_IPS`.
- Do not queue for a slot inside the handler without a new ADR.
- Change `SearchConfig` limits and `frontend/lib/search.ts` together.
- Regression tests that must keep passing: `test_concurrent_burst_admits_only_the_cap`, `test_total_deadline_stops_the_postgres_query`, `test_client_disconnect_stops_the_postgres_query`, `test_frontend_query_limits_match_the_backend`.

## Question for nish
Are 60 searches per minute with a burst of 20, and 16 concurrent searches per worker, the numbers you want at launch, or were they only starting values?
