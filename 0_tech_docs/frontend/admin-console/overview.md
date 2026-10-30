# Admin console and backend proxy

Area: frontend · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `frontend/app/admin/`
- `frontend/app/api/admin/`
- `frontend/components/admin/`
- `frontend/lib/crawler-proxy.ts`
- `frontend/lib/axios.js` (every axios instance: `api` for the browser, `backend` for FastAPI and GitHub)

## How-it-works docs
- _none yet_

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Server routes hold the service key; the browser never sees it
- [ ] Backend base derived from `CRAWLER_REPORT_API_URL`

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._

- HTTP goes through axios, not raw `fetch`: browser components use `api` and server routes use `backend` / `adminGet`, all from `lib/axios.js`; `backend` keeps the fetch adapter, `cache: "no-store"`, `redirect: "error"` and the timeouts. Both clients resolve every status, so check `response.status` and map errors yourself.
