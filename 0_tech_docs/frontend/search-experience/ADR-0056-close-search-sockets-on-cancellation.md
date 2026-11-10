---
id: ADR-0056
title: Use Axios Node HTTP transport for cancellable search requests
status: accepted
date: 2026-11-09
area: frontend
feature: search-experience
code: [frontend/lib/axios.js, frontend/app/api/search/route.ts, frontend/app/api/search/suggest/route.ts]
related: [ADR-0031, ADR-0046, INC-0033, INC-0040]
---

# ADR-0056: Close upstream search sockets on cancellation

## Context

The clean Linux stack run reproduced the remaining socket risk in INC-0033:
Next's request signal and Axios's composed signal aborted, and the proxy's
promise rejected, but a real blocked PostgreSQL query continued until its
statement deadline. Returning promptly from a proxy is insufficient evidence
that FastAPI cancelled its database work.

## Decision

Keep the shared typed Axios client/factory. For public search and suggestions,
apply the centralized `searchRequestOptions`: Node HTTP adapter, zero redirects,
and no environment HTTP proxy. Explicit caller deadlines and request signals
remain in place. The HTTP adapter destroys the upstream request on abort and
bypasses Next's patched fetch. Node HTTP does not participate in Next's data
cache; proxy responses retain `Cache-Control: no-store`.

Other server calls retain the existing fetch adapter and `abortableFetch`;
browser calls retain the fetch adapter. This narrowly addresses measured search
cancellation behavior without changing authentication/provider transports.
These search handlers require the existing default Node runtime, not Edge.

## Alternatives

- Racing fetch against abort bounds proxy response time but does not guarantee
  socket closure (observed in INC-0040).
- Raising the cancellation test timeout would hide the failure by waiting for
  the database's three-second statement timeout; rejected.
- Replacing every server transport would expand the change into GitHub OAuth
  and provider behavior without evidence that those flows need it; deferred.

## Verification and consequences

The fresh-stack test locks real search/vocabulary tables, waits for each query
to block, cancels twelve alternating search/suggestion browser requests, and
requires PostgreSQL waiters to disappear before the existing 2.5-second bound.
It verifies concurrency-slot recovery after releasing the lock. Frontend socket
integration repeats cancellation and refuses upstream redirects; cold-server
timeouts, rate limits, validation, overview bridging, and authentication suites
must continue passing. No new dependencies or ranking behavior change.

## Rules for future changes

- Search/suggestion requests must use `searchRequestOptions` and the browser signal.
- Test actual upstream closure and PostgreSQL cancellation, not promise rejection alone.
- Keep redirects disabled and deadlines below the public request timeout.
