---
id: ADR-0031
title: Use a validated same-origin search bridge with explicit demo mode
status: accepted
date: '2026-11-02'
area: frontend
feature: search-experience
code:
- frontend/app/api/search/route.ts
- frontend/lib/axios.js
- frontend/lib/search.ts
- frontend/components/search-experience.tsx
- frontend/lib/demo.ts
supersedes: null
superseded_by: null
related:
- ADR-0003
- ADR-0023
- ADR-0032
---

# ADR-0031: Use a validated same-origin search bridge with explicit demo mode

## TL;DR

The browser calls /api/search; the Next.js server validates requests and backend responses. Missing BACKEND_URL selects a labeled demo collection, while live backend errors stay errors.

## Context

Frontend development began before the backend search endpoint. A usable demo was needed without pretending that canned results were live indexed content.

## Decision

Validate q (1–300 characters) and source categories in the bridge. With BACKEND_URL, call /search with a 10-second timeout, require valid result shapes, and mark mode=live. Otherwise return mode=demo. Responses are no-store. Central Axios clients use the fetch adapter; server requests refuse redirects and preserve the abort signal through Next fetch. UI requests cancel superseded searches; saved results use localStorage. Pasted-code preview is presentation, not a completed backend code-mode integration.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Same-origin bridge with explicit demo | Stable browser contract and server-held configuration | Extra HTTP hop | chosen |
| Browser talks directly to upstream/backend | One fewer hop | Exposes connection policy and duplicates error handling | rejected for this UI |
| Silently replace live failures with demo data | Always shows results | Misrepresents availability and relevance | rejected |

## Why

The bridge lets the frontend ship independently while keeping the data source and errors honest. A local bookmark list avoids inventing a user-account service for the MVP.

## Consequences

- Gained: Validated response boundaries, clear error modes and cancellable UI work.
- Accepted limitations / tech debt: Bookmarks are browser-local, not synced accounts; there is no cache-based speedup or full pagination contract.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Live failures never become demo successes.
- Browser calls use same-origin API routes.
- Abort/cancellation cannot let an older request replace a newer result.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Axios transition and signal rationale: [08c73e3](https://github.com/nishchup489-afk/developers_eye/commit/08c73e3484b1409d832c8a54c234e54cb436fea7).

- [`frontend/app/api/search/route.ts`](../../../frontend/app/api/search/route.ts)
- [`frontend/lib/axios.js`](../../../frontend/lib/axios.js)
- [`frontend/lib/search.ts`](../../../frontend/lib/search.ts)
- [`frontend/components/search-experience.tsx`](../../../frontend/components/search-experience.tsx)
- [`frontend/lib/demo.ts`](../../../frontend/lib/demo.ts)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`frontend/tests/integration.mjs`](../../../frontend/tests/integration.mjs)
- [`frontend/tests/admin-routes.mjs`](../../../frontend/tests/admin-routes.mjs)

## Revisit when

- Before introducing caching, account-synced saves, pagination or backend search modes.

## Rules for future changes

- Change backend response schemas and frontend validators together.
- Keep timeout, no-store and redirect behavior when changing the HTTP abstraction.
