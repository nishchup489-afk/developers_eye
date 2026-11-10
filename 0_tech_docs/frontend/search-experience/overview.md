# Public search, code preview and local saves

Area: frontend · Status: active

## Purpose

The frontend displays a validated live/demo contract, cancels superseded requests, and saves results locally. Code preview affects presentation; it does not prove that backend code routing or exact-symbol retrieval is active.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`frontend/components/search-experience.tsx`](../../../frontend/components/search-experience.tsx)
- [`frontend/app/api/search/route.ts`](../../../frontend/app/api/search/route.ts)
- [`frontend/app/api/search/suggest/route.ts`](../../../frontend/app/api/search/suggest/route.ts) ("Did you mean", see [ADR-0045](../../backend/fuzzy-correction/ADR-0045-did-you-mean-with-surface-word-suggestions.md))
- [`frontend/lib/search.ts`](../../../frontend/lib/search.ts)
- [`frontend/lib/axios.js`](../../../frontend/lib/axios.js)

## How-it-works docs

- [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0031](ADR-0031-same-origin-search-and-explicit-demo.md) | decision | Use a validated same-origin search bridge with explicit demo mode | accepted |
| [ADR-0048](ADR-0048-ground-ai-overviews-in-signed-results.md) | decision | Ground AI overviews in signed search results with bounded Groq usage | superseded |
| [ADR-0049](../../backend/ai-overview/ADR-0049-backend-owned-overviews-with-shared-postgres-budgets.md) | decision | Own AI overviews in FastAPI with shared PostgreSQL budgets | accepted |
| [INC-0033](INC-0033-upstream-timeout-ignored-on-first-hung-request.md) | incident | Upstream timeout ignored on a Next.js server's first hung request | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Preserve explicit language preference, source/version/observation metadata,
  and bounded shareable paging as specified in ADR-0053.

- Change backend response schemas and frontend validators together.
- Keep timeout, no-store and redirect behavior when changing the HTTP abstraction.
- Do not remove `abortableFetch` in `lib/axios.js` or call FastAPI with bare `fetch`; re-run `npm run test:integration` (cold-start timeout case) after Next.js upgrades (INC-0033).
- Only offer spelling suggestions; never rewrite the user's query (ADR-0045).
- AI overview generation, signing, validation, provider credentials and quotas belong in FastAPI; frontend code only renders/proxies the backend contract (ADR-0049).
- Render model text as plain text. Preserve the backend's status and Retry-After; forward only the documented ingress headers. See the [AI overview feature](../../backend/ai-overview/overview.md).
