---
id: INC-0038
title: Stale Next.js dev chunks left pages unhydrated until a hard refresh
status: mitigated
date: 2026-11-10
severity: medium
area: infra
feature: local-dev-and-testing
code: [frontend/next.config.ts]
fix_commits: []
related: []
---

# INC-0038: Stale Next.js dev chunks left pages unhydrated until a hard refresh

## Signature

```
Uncaught (in promise) Error: Module [project]/node_modules/next/dist/compiled/@next/react-refresh-utils/dist/runtime.js [app-client] (ecmascript) was instantiated as a runtime entry of chunk static/chunks/turbopack-_11q0wbt2n0d9y._.js, but the module factory is not available.
This is often caused by a stale browser cache, misconfigured Cache-Control headers, or a service worker serving outdated responses.
```

## Summary

On `npm run dev`, the first visit to `localhost:3000`, and going from `/admin` back to
the home page, rendered the server HTML only: no eye, unstyled search mode buttons, dead
buttons and search, and admin pages that showed their loading state forever (their data
is fetched by client JavaScript). Ctrl+Shift+R always fixed it.

## Expected vs actual

- Expected: pages hydrate on a normal load or navigation in development.
- Actual: the browser ran an old copy of a Turbopack dev chunk, the client runtime threw,
  and React never hydrated.

## Timeline

Reported as "429 on first load". The 429 could not be found again; the browser console
showed the error above instead.

## Root cause

Turbopack names dev chunks by content of the chunk graph, not by build, so the same URL
(`turbopack-_11q0wbt2n0d9y._.js`) is served across dev server runs and is identical across
machines. Next serves dev chunks with `Cache-Control: no-cache, must-revalidate` and a weak
ETag of size + mtime. Anything that answers for that URL without asking the server (a service
worker registered on `localhost:3000` by another project, or a cached response whose ETag
still matches) hands back a copy that lists module factories the current server never sent.
A hard refresh bypasses both the HTTP cache and service workers, which is why it always worked.

Not reproduced in a Linux sandbox with Chromium (fresh profile, prod build then dev on the same
profile, `next build` while dev runs, edits between dev restarts): revalidation returned correct
304s every time. The exact stale source on the reporting machine (Windows, Brave) is unconfirmed.

## Fixes that did not work

| Attempt | Why it failed |
| --- | --- |
| Looking for the backend search rate limiter (HTTP 429) | Not involved: admin pages never call it and no 429 appeared once the console was checked. |

## Resolution

`frontend/next.config.ts` sends `Cache-Control: no-store, must-revalidate` for
`/_next/static/*` in development only, so the browser never keeps a dev chunk to reuse.
Production keeps Next's immutable caching of hashed chunks.

A service worker is not affected by this header. If the error persists, open DevTools ->
Application -> Service workers, unregister anything on `localhost:3000`, and Clear site data.
This app registers no service worker.

## Prevention

- Regression test: none (needs a real browser with the stale state).
- Monitoring / alert: none; the console error above is the signal.
- Design change (ADR): none.
- Remaining risk: a foreign service worker on port 3000 still serves stale chunks.

## Rules for future changes

- Keep dev chunks uncacheable in `next.config.ts`; do not add long caching for `/_next/static` in development.
- Do not register a service worker without versioned cache names and a dev-mode bypass.
- When a page renders but nothing is clickable, check the browser console before the backend.
