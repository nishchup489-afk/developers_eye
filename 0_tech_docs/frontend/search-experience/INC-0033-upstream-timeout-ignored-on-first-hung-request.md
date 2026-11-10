---
id: INC-0033
title: Upstream timeout ignored on a Next.js server's first hung request
status: resolved
date: '2026-11-07'
severity: medium
area: frontend
feature: search-experience
code:
- frontend/lib/axios.js:abortableFetch
- frontend/tests/integration.mjs
fix_commits:
- 17e62be
related:
- ADR-0031
- ADR-0045
---

# INC-0033: Upstream timeout ignored on a Next.js server's first hung request

## Signature

```
TypeError: fetch failed
  [cause]: HeadersTimeoutError: Headers Timeout Error
    code: 'UND_ERR_HEADERS_TIMEOUT'
    at async get (frontend/tests/integration.mjs) ... await get(live, { q: "timeout" }, 504)
```

The `/api/search` call to a backend that never answers hangs until the client gives up (undici's 300 s headers timeout in the test), instead of returning 504 after 10 s.

## Summary

The `backend` axios client sets a timeout (10 s for search, 5 s for suggestions). On a freshly started `next start` process, the **first** request whose upstream never responded did not time out. Later requests in the same process timed out correctly. In production this means the first stalled FastAPI call after a deploy or restart holds the browser request open indefinitely. It turned up while adding the suggestion tests (ADR-0045): `npm run test:integration` hung for about 5 minutes.

## Expected vs actual

- Expected: `GET /api/search?q=…` with a hung upstream returns 504 "Search timed out" after 10 s, every time.
- Actual: the first such request in a server process never settles; the second returns 504 after 10 s.

## Timeline

1. The extended `integration.mjs` hung at the existing `get(live, { q: "timeout" }, 504)`. The original test file passed against the same build.
2. A probe script (start server, hit a hanging mock) reproduced it on the original `/api/search` route: first call hung (client aborted at 20 s), second 504 at 10 s.
3. Removing the new demo-suggestion calls made the original timeout pass again, but runs stayed flaky. So the bug is timing-dependent and not caused by the new route.
4. Instrumenting `env.fetch` showed the `Request` and its signal were passed through, and the signal **did abort at 10 000 ms**, yet the patched `fetch` promise never settled.

## Root cause

Next.js 16's patched global `fetch` (`__nextPatched`) can ignore the abort signal on the process's first hanging request, so the fetch never rejects even though axios's composed timeout signal fires. axios waits on the `fetch` promise, so its timeout never surfaces. The existing workaround in `lib/axios.js` (passing `input.signal` as `init.signal`, because Next's fetch only reads `init.signal`) was necessary but not enough.

Evidence: the logged `ABORTED 10000` with no settlement on the first call, and correct 504s on later calls in the same process. The exact internal reason in Next is not pinned down.

## Fixes that did not work

| Attempt | Why it failed |
| --- | --- |
| Checking that the signal reaches `fetch` (`input instanceof Request` → `input.signal`) | It already did: `instanceof` was true and the signal was present; the patched fetch still ignored it |
| Reordering or removing test calls | Changed timing only; the hang came back on other runs |

## Resolution

`backend` now uses `env: { fetch: abortableFetch }`. `abortableFetch` still calls `fetch(input, { ...init, signal })`, but races the result against the signal: when the signal aborts, the returned promise rejects with `signal.reason`, which is axios's `ETIMEDOUT` error, so `isTimeout()` is true and routes return 504. The underlying fetch is left to Next; its rejection is consumed, so no unhandled rejection.

Verified: the probe returns 504 at 10 s (search) and 5 s (suggest) on a cold server's first request; `test:integration`, `test:admin`, `test:admin:routes` and the unit suites all pass.

## Prevention

- Regression test: `frontend/tests/integration.mjs` hits a hung upstream for `/api/search` and `/api/search/suggest` on the live server. The suggest route's first hung request is exactly the cold-start case.
- Monitoring / alert: none. A 504 rate on `/api/search*` would show the fix working; a request that never ends would not show up as a status at all.
- Design change (ADR): none. ADR-0031's timeout rule now relies on `abortableFetch`.
- Remaining risk: the abandoned underlying fetch may hold a socket until Node gives it up. Acceptable for an upstream that is already hung.

## Rules for future changes

2026-11-09 follow-up: [INC-0040](INC-0040-aborted-search-left-postgres-waiting.md)
reproduced the remaining socket risk on Linux. Search and suggestion requests
now use the Node HTTP options in ADR-0056. Other fetch-based calls retain this
incident's promise-settlement workaround.

- Every server-side HTTP call goes through the `backend` client in `frontend/lib/axios.js`; do not call `fetch` to FastAPI directly.
- Do not remove `abortableFetch` or switch the `env.fetch` without re-running the cold-start timeout test (a fresh `next start`, then a hung upstream first).
- When upgrading Next.js, re-run `npm run test:integration`; it covers this case.
