# Admin authentication

Area: frontend · Status: active

## Purpose

GitHub OAuth plus an ID allowlist establishes a signed-cookie admin session. Service credentials stay in server requests and every admin request is re-authorized.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`frontend/lib/admin-session.ts`](../../../frontend/lib/admin-session.ts)
- [`frontend/lib/admin-auth.ts`](../../../frontend/lib/admin-auth.ts)
- [`frontend/app/api/auth`](../../../frontend/app/api/auth)

## How-it-works docs

- [`frontend/README.md`](../../../frontend/README.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0032](ADR-0032-github-admin-auth-and-service-key-boundary.md) | decision | Authenticate admins with GitHub and keep the backend key behind server routes | accepted |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Keep OAuth state/PKCE and signed-cookie checks covered by regression tests.
- Rotate exposed credentials; deleting a tracked file alone is not remediation.
