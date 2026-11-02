---
id: ADR-0032
title: Authenticate admins with GitHub and keep the backend key behind server routes
status: accepted
date: '2026-11-02'
area: frontend
feature: admin-auth
code:
- frontend/lib/admin-session.ts
- frontend/lib/admin-auth.ts
- frontend/lib/crawler-proxy.ts
- frontend/app/api/auth/github/route.ts
- frontend/app/api/auth/github/callback/route.ts
supersedes: null
superseded_by: null
related:
- ADR-0030
- INC-0006
---

# ADR-0032: Authenticate admins with GitHub and keep the backend key behind server routes

## TL;DR

GitHub OAuth establishes an allowlisted admin identity; a signed HttpOnly cookie carries the session. Only server routes attach the shared backend reporting key.

## Context

The admin console needs a small operator access model without building passwords or exposing a service credential to the browser.

## Decision

OAuth uses state and S256 PKCE. Session cookies expire after eight hours, are signed with HMAC-SHA256, and are checked against ADMIN_GITHUB_IDS on each request. Production origins require HTTPS; cookies use HttpOnly, SameSite=Lax and Secure for HTTPS. Session signing gives integrity, not encryption. Admin proxy routes validate the session, derive the backend admin path from CRAWLER_REPORT_API_URL and use private/no-store plus Vary: Cookie. Upstream redirects are refused.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| OAuth allowlist plus signed session | Small operator surface, no password store | Shared backend key and stateless session trade-offs | chosen |
| Expose the service key to browser code | Simple direct fetches | Anyone with browser access can extract it | rejected |
| Full custom identity platform now | Fine-grained roles and revocation | Large unrelated MVP scope | deferred |

## Why

User identity and service-to-service authentication are separate boundaries. Per-request allowlist checks let operator access be removed without waiting only for cookie expiry.

## Consequences

- Gained: Server-side secrets and explicit operator identity checks.
- Accepted limitations / tech debt: There is no per-session revocation store or granular backend role model; a compromised shared key remains a serious incident (INC-0006).
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- No secret is NEXT_PUBLIC or serialized into browser responses.
- Cookie signature, purpose, expiry and allowlist checks all succeed before proxying.
- Admin responses are not publicly cacheable.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`frontend/lib/admin-session.ts`](../../../frontend/lib/admin-session.ts)
- [`frontend/lib/admin-auth.ts`](../../../frontend/lib/admin-auth.ts)
- [`frontend/lib/crawler-proxy.ts`](../../../frontend/lib/crawler-proxy.ts)
- [`frontend/app/api/auth/github/route.ts`](../../../frontend/app/api/auth/github/route.ts)
- [`frontend/app/api/auth/github/callback/route.ts`](../../../frontend/app/api/auth/github/callback/route.ts)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`frontend/tests/admin-unit.mjs`](../../../frontend/tests/admin-unit.mjs)
- [`frontend/tests/admin-routes.mjs`](../../../frontend/tests/admin-routes.mjs)
- [`frontend/tests/admin-integration.mjs`](../../../frontend/tests/admin-integration.mjs)

## Revisit when

- Before adding multiple operator roles or write actions.
- A requirement appears for immediate per-session revocation.

## Rules for future changes

- Keep OAuth state/PKCE and signed-cookie checks covered by regression tests.
- Rotate exposed credentials; deleting a tracked file alone is not remediation.
