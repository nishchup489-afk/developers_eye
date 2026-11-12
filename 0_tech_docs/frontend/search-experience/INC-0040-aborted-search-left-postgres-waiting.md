---
id: INC-0040
title: Aborted Linux search left its PostgreSQL query waiting
status: resolved
date: 2026-11-09
severity: medium
area: frontend
feature: search-experience
code: [frontend/lib/axios.js, frontend/tests/integration.mjs, scripts/e2e_search_stack.py]
related: [INC-0033, ADR-0056]
---

# INC-0040: Proxy abort did not reliably close the upstream socket

## Reproduction and evidence

Fresh Ubuntu 26.04/WSL, official Node 24.15.0, Next 16.4.5, PostgreSQL 18.6,
and an empty migrated database. Run `e2e_search_stack.py` after the production
build. Ordinary search, paging, filters, deadlines and overload checks pass.
The third repeated disconnected browser request can leave a real SELECT blocked
on `search_index` beyond the 2.5-second cancellation assertion. Two independent
runs reproduced this; the Windows run had passed.

Instrumentation confirmed both the Next request abort event and Axios's abort
event fired. `pg_stat_activity` still showed an active relation-lock waiter.
Direct FastAPI cancellation stopped its waiter in about 35 ms in the diagnostic
probe. The observed boundary is the fetch-based Next-to-FastAPI transport;
the exact Next/undici internal cause was not established.

## Resolution

Apply ADR-0056's Axios Node HTTP options to search and suggestions. This closes
the upstream socket on abort while preserving deadline, validation, no-cache,
and zero-redirect behavior. Keep the earlier `abortableFetch` workaround for
the server calls that still use fetch. Do not relax the cancellation deadline.

## Regression coverage

`e2e_search_stack.py` now cancels twelve alternating search/suggestion requests
while both real tables are locked, verifies waiters clear before the unchanged
deadline, and verifies slots recover. `frontend/tests/integration.mjs` repeats
mock-upstream socket cancellation twelve times and tests redirect refusal.
The overview bridge test uses an actual local HTTP server for the search token
request, covering the production adapter rather than mocking global fetch.
