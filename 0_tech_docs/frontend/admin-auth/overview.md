# Admin authentication

Area: frontend · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `frontend/lib/admin-auth.ts`
- `frontend/lib/admin-session.ts`
- `frontend/app/api/auth/`
- `frontend/app/admin/login/`

## How-it-works docs
- _none yet_

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] GitHub OAuth with state and S256 PKCE
- [ ] Signed HttpOnly session cookie (8 h) checked against `ADMIN_GITHUB_IDS` on every request

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
