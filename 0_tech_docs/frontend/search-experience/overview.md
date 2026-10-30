# Search experience and demo mode

Area: frontend · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `frontend/app/search/`
- `frontend/app/api/search/`
- `frontend/components/search-experience.tsx`
- `frontend/lib/search.ts`
- `frontend/lib/demo.ts`
- `frontend/lib/api-client.ts` (browser axios client) and `frontend/lib/backend-client.ts` (server axios client)

## How-it-works docs
- _none yet_

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Same-origin `/api/search` proxy with demo fallback when `BACKEND_URL` is unset
- [ ] Saved results in `localStorage`

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
