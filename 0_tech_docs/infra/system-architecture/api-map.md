# API map

Generated from the code by [`scripts/update_api_map.py`](../../../scripts/update_api_map.py). Do not edit between the markers; change the code and run:

```bash
python scripts/update_api_map.py          # rewrite this file
python scripts/update_api_map.py --check  # exit 1 if stale or a call reaches no route
```

The pre-commit hook runs it, so the map follows every commit. It answers three questions: what is exposed to third parties (section 1), which frontend call reaches which backend endpoint and in which files (section 2), and the full route lists (sections 3 and 4). The public, hand-written contract for API users is [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md).

<!-- api-map:start -->

## 1. Who can reach what

In [`deploy/docker-compose.yml`](../../../deploy/docker-compose.yml), only these services publish ports: `caddy` (80:80, 443:443).
Caddy forwards every request to `web:3000` (the Next.js app), so **third parties on the internet can call only the Next.js routes**.
The FastAPI service `api` publishes no port: it is reachable only from other containers (the Next.js server, workers).
`web` reaches FastAPI through `BACKEND_URL=http://api:8000`, `CRAWLER_REPORT_API_URL=http://api:8000`.
FastAPI CORS allows browser calls only from `http://127.0.0.1:3000`, `http://localhost:3000`, `http://127.0.0.1:4173`, `http://localhost:4173` (local development).

### Public: no credentials

| Layer | Method | Path | Accepts | Source |
| --- | --- | --- | --- | --- |
| Next.js (internet) | GET | `/api/auth/github` | — | [`frontend/app/api/auth/github/route.ts`](../../../frontend/app/api/auth/github/route.ts) |
| Next.js (internet) | GET | `/api/auth/github/callback` | `code`, `state` | [`frontend/app/api/auth/github/callback/route.ts`](../../../frontend/app/api/auth/github/callback/route.ts) |
| Next.js (internet) | POST | `/api/auth/logout` | — | [`frontend/app/api/auth/logout/route.ts`](../../../frontend/app/api/auth/logout/route.ts) |
| Next.js (internet) | GET | `/api/search` | `mode`, `page`, `q`, `source` | [`frontend/app/api/search/route.ts`](../../../frontend/app/api/search/route.ts) |
| Next.js (internet) | GET | `/api/search/suggest` | `q` | [`frontend/app/api/search/suggest/route.ts`](../../../frontend/app/api/search/suggest/route.ts) |
| FastAPI (internal in prod) | GET | `/` | — | [`backend/src/backend/main.py:91`](../../../backend/src/backend/main.py#L91) |
| FastAPI (internal in prod) | GET | `/health` | — | [`backend/src/backend/main.py:96`](../../../backend/src/backend/main.py#L96) |
| FastAPI (internal in prod) | GET | `/health/db` | — | [`backend/src/backend/main.py:101`](../../../backend/src/backend/main.py#L101) |
| FastAPI (internal in prod) | GET | `/search` | `q` (query: str, max_length=1024, required)<br>`source` (query: SearchFilter \| None, default None)<br>`limit` (query: int, ge=1, le=50, default 20)<br>`page` (query: int, ge=1, default 1)<br>`mode` (query: SearchMode, default SearchMode.ALL) | [`backend/src/backend/api/search.py:43`](../../../backend/src/backend/api/search.py#L43) |
| FastAPI (internal in prod) | GET | `/search/suggest` | `q` (query: str, max_length=1024, required) | [`backend/src/backend/api/search.py:94`](../../../backend/src/backend/api/search.py#L94) |

### Admin: needs credentials

| Layer | Method | Path | Credential | Source |
| --- | --- | --- | --- | --- |
| Next.js (internet) | GET | `/api/admin/crawler/inspect` | viewer session (signed cookie) | [`frontend/app/api/admin/crawler/inspect/route.ts`](../../../frontend/app/api/admin/crawler/inspect/route.ts) |
| Next.js (internet) | GET | `/api/admin/crawler/monitor` | viewer session (signed cookie) | [`frontend/app/api/admin/crawler/monitor/route.ts`](../../../frontend/app/api/admin/crawler/monitor/route.ts) |
| Next.js (internet) | GET | `/api/admin/crawler/report` | viewer session (signed cookie) | [`frontend/app/api/admin/crawler/report/route.ts`](../../../frontend/app/api/admin/crawler/report/route.ts) |
| Next.js (internet) | GET | `/api/admin/indexer/report` | viewer session (signed cookie) | [`frontend/app/api/admin/indexer/report/route.ts`](../../../frontend/app/api/admin/indexer/report/route.ts) |
| Next.js (internet) | GET | `/api/admin/indexer/vocabulary` | viewer session (signed cookie) | [`frontend/app/api/admin/indexer/vocabulary/route.ts`](../../../frontend/app/api/admin/indexer/vocabulary/route.ts) |
| Next.js (internet) | GET | `/api/admin/system/corpus` | viewer session (signed cookie) | [`frontend/app/api/admin/system/corpus/route.ts`](../../../frontend/app/api/admin/system/corpus/route.ts) |
| Next.js (internet) | GET | `/api/admin/system/hosts` | viewer session (signed cookie) | [`frontend/app/api/admin/system/hosts/route.ts`](../../../frontend/app/api/admin/system/hosts/route.ts) |
| Next.js (internet) | GET | `/api/admin/system/problems` | viewer session (signed cookie) | [`frontend/app/api/admin/system/problems/route.ts`](../../../frontend/app/api/admin/system/problems/route.ts) |
| Next.js (internet) | GET | `/api/admin/system/report` | viewer session (signed cookie) | [`frontend/app/api/admin/system/report/route.ts`](../../../frontend/app/api/admin/system/report/route.ts) |
| Next.js (internet) | GET | `/api/admin/system/search` | viewer session (signed cookie) | [`frontend/app/api/admin/system/search/route.ts`](../../../frontend/app/api/admin/system/search/route.ts) |
| FastAPI (internal in prod) | GET | `/admin/crawler/attempts/{attempt_id}` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/crawler_report.py:89`](../../../backend/src/backend/api/crawler_report.py#L89) |
| FastAPI (internal in prod) | GET | `/admin/crawler/documents/{document_id}` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/crawler_report.py:83`](../../../backend/src/backend/api/crawler_report.py#L83) |
| FastAPI (internal in prod) | GET | `/admin/crawler/monitor` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/crawler_report.py:64`](../../../backend/src/backend/api/crawler_report.py#L64) |
| FastAPI (internal in prod) | GET | `/admin/crawler/report` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/crawler_report.py:32`](../../../backend/src/backend/api/crawler_report.py#L32) |
| FastAPI (internal in prod) | GET | `/admin/indexer/report` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/indexer_report.py:13`](../../../backend/src/backend/api/indexer_report.py#L13) |
| FastAPI (internal in prod) | GET | `/admin/indexer/vocabulary` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/indexer_report.py:23`](../../../backend/src/backend/api/indexer_report.py#L23) |
| FastAPI (internal in prod) | GET | `/admin/system/corpus` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/system_report.py:32`](../../../backend/src/backend/api/system_report.py#L32) |
| FastAPI (internal in prod) | GET | `/admin/system/hosts` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/system_report.py:26`](../../../backend/src/backend/api/system_report.py#L26) |
| FastAPI (internal in prod) | GET | `/admin/system/problems` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/system_report.py:52`](../../../backend/src/backend/api/system_report.py#L52) |
| FastAPI (internal in prod) | GET | `/admin/system/report` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/system_report.py:20`](../../../backend/src/backend/api/system_report.py#L20) |
| FastAPI (internal in prod) | GET | `/admin/system/search` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | [`backend/src/backend/api/system_report.py:38`](../../../backend/src/backend/api/system_report.py#L38) |

A *viewer session* ([`frontend/lib/admin-session.ts`](../../../frontend/lib/admin-session.ts)) is granted to GitHub ids in `ADMIN_GITHUB_IDS` or `ADMIN_VIEWER_GITHUB_IDS`; with `ADMIN_VIEWER_ACCESS=github` to any GitHub account, and with `ADMIN_VIEWER_ACCESS=public` to anyone without signing in. So with `public`, every Next.js admin route above is effectively a third-party API.

> **Config warning:** `web` sets `CRAWLER_REPORT_API_URL=http://api:8000` in `deploy/docker-compose.yml`, but the admin routes need it to end with `/admin/crawler/report` (e.g. `http://api:8000/admin/crawler/report`); otherwise every admin page gets 503/502.

## 2. Frontend → backend: which call reaches which endpoint

One row per browser call site. The browser only talks to Next.js; the Next.js route then calls FastAPI or an external service.

| Browser call (file) | Next.js route (file) | Calls upstream | Upstream handler (file) |
| --- | --- | --- | --- |
| GET `/api/admin/crawler/inspect` via axios `api` client<br>[`frontend/components/admin/crawl-inspector.tsx:45`](../../../frontend/components/admin/crawl-inspector.tsx#L45) | `/api/admin/crawler/inspect`<br>[`frontend/app/api/admin/crawler/inspect/route.ts`](../../../frontend/app/api/admin/crawler/inspect/route.ts) | FastAPI GET `/admin/crawler/attempts/{attempt_id}`<br>FastAPI GET `/admin/crawler/documents/{document_id}`<br>`crawlerProxy` → `adminProxy` → `adminGet` (Bearer key), [`line 11`](../../../frontend/app/api/admin/crawler/inspect/route.ts#L11) | `crawler_attempt` [`backend/src/backend/api/crawler_report.py:89`](../../../backend/src/backend/api/crawler_report.py#L89)<br>`crawler_document` [`backend/src/backend/api/crawler_report.py:83`](../../../backend/src/backend/api/crawler_report.py#L83) |
| GET `/api/admin/crawler/monitor` via `usePolling` → axios `api` client<br>[`frontend/components/admin/crawler-control-center.tsx:79`](../../../frontend/components/admin/crawler-control-center.tsx#L79) | `/api/admin/crawler/monitor`<br>[`frontend/app/api/admin/crawler/monitor/route.ts`](../../../frontend/app/api/admin/crawler/monitor/route.ts) | FastAPI GET `/admin/crawler/monitor`<br>`crawlerProxy` → `adminProxy` → `adminGet` (Bearer key), [`line 33`](../../../frontend/app/api/admin/crawler/monitor/route.ts#L33) | `crawler_monitor` [`backend/src/backend/api/crawler_report.py:64`](../../../backend/src/backend/api/crawler_report.py#L64) |
| GET `/api/admin/crawler/report` via `usePolling` → axios `api` client<br>[`frontend/components/admin/crawler-control-center.tsx:80`](../../../frontend/components/admin/crawler-control-center.tsx#L80) | `/api/admin/crawler/report`<br>[`frontend/app/api/admin/crawler/report/route.ts`](../../../frontend/app/api/admin/crawler/report/route.ts) | FastAPI GET `/admin/crawler/report`<br>`adminGet` on `$CRAWLER_REPORT_API_URL` (Bearer key), [`line 27`](../../../frontend/app/api/admin/crawler/report/route.ts#L27) | `crawler_report` [`backend/src/backend/api/crawler_report.py:32`](../../../backend/src/backend/api/crawler_report.py#L32) |
| GET `/api/admin/crawler/report` via axios `api` client<br>[`frontend/components/admin/crawler-dashboard.tsx:38`](../../../frontend/components/admin/crawler-dashboard.tsx#L38) | `/api/admin/crawler/report`<br>[`frontend/app/api/admin/crawler/report/route.ts`](../../../frontend/app/api/admin/crawler/report/route.ts) | FastAPI GET `/admin/crawler/report`<br>`adminGet` on `$CRAWLER_REPORT_API_URL` (Bearer key), [`line 27`](../../../frontend/app/api/admin/crawler/report/route.ts#L27) | `crawler_report` [`backend/src/backend/api/crawler_report.py:32`](../../../backend/src/backend/api/crawler_report.py#L32) |
| GET `/api/admin/indexer/report` via `usePolling` → axios `api` client<br>[`frontend/components/admin/crawler-control-center.tsx:81`](../../../frontend/components/admin/crawler-control-center.tsx#L81) | `/api/admin/indexer/report`<br>[`frontend/app/api/admin/indexer/report/route.ts`](../../../frontend/app/api/admin/indexer/report/route.ts) | FastAPI GET `/admin/indexer/report`<br>`adminProxy` → `adminGet` (Bearer key), [`line 14`](../../../frontend/app/api/admin/indexer/report/route.ts#L14) | `indexer_report` [`backend/src/backend/api/indexer_report.py:13`](../../../backend/src/backend/api/indexer_report.py#L13) |
| GET `/api/admin/indexer/report` via `usePolling` → axios `api` client<br>[`frontend/components/admin/indexer-control-center.tsx:21`](../../../frontend/components/admin/indexer-control-center.tsx#L21) | `/api/admin/indexer/report`<br>[`frontend/app/api/admin/indexer/report/route.ts`](../../../frontend/app/api/admin/indexer/report/route.ts) | FastAPI GET `/admin/indexer/report`<br>`adminProxy` → `adminGet` (Bearer key), [`line 14`](../../../frontend/app/api/admin/indexer/report/route.ts#L14) | `indexer_report` [`backend/src/backend/api/indexer_report.py:13`](../../../backend/src/backend/api/indexer_report.py#L13) |
| GET `/api/admin/indexer/vocabulary` via `usePolling` → axios `api` client<br>[`frontend/components/admin/vocabulary-report.tsx:15`](../../../frontend/components/admin/vocabulary-report.tsx#L15) | `/api/admin/indexer/vocabulary`<br>[`frontend/app/api/admin/indexer/vocabulary/route.ts`](../../../frontend/app/api/admin/indexer/vocabulary/route.ts) | FastAPI GET `/admin/indexer/vocabulary`<br>`adminProxy` → `adminGet` (Bearer key), [`line 14`](../../../frontend/app/api/admin/indexer/vocabulary/route.ts#L14) | `vocabulary_report` [`backend/src/backend/api/indexer_report.py:23`](../../../backend/src/backend/api/indexer_report.py#L23) |
| GET `/api/admin/system/corpus` via `usePolling` → axios `api` client<br>[`frontend/components/admin/corpus-control-center.tsx:16`](../../../frontend/components/admin/corpus-control-center.tsx#L16) | `/api/admin/system/corpus`<br>[`frontend/app/api/admin/system/corpus/route.ts`](../../../frontend/app/api/admin/system/corpus/route.ts) | FastAPI GET `/admin/system/corpus`<br>`adminProxy` → `adminGet` (Bearer key), [`line 8`](../../../frontend/app/api/admin/system/corpus/route.ts#L8) | `corpus_report` [`backend/src/backend/api/system_report.py:32`](../../../backend/src/backend/api/system_report.py#L32) |
| GET `/api/admin/system/hosts` via `usePolling` → axios `api` client<br>[`frontend/components/admin/hosts-control-center.tsx:16`](../../../frontend/components/admin/hosts-control-center.tsx#L16) | `/api/admin/system/hosts`<br>[`frontend/app/api/admin/system/hosts/route.ts`](../../../frontend/app/api/admin/system/hosts/route.ts) | FastAPI GET `/admin/system/hosts`<br>`adminProxy` → `adminGet` (Bearer key), [`line 14`](../../../frontend/app/api/admin/system/hosts/route.ts#L14) | `host_report` [`backend/src/backend/api/system_report.py:26`](../../../backend/src/backend/api/system_report.py#L26) |
| GET `/api/admin/system/problems` via `usePolling` → axios `api` client<br>[`frontend/components/admin/problems-banner.tsx:13`](../../../frontend/components/admin/problems-banner.tsx#L13) | `/api/admin/system/problems`<br>[`frontend/app/api/admin/system/problems/route.ts`](../../../frontend/app/api/admin/system/problems/route.ts) | FastAPI GET `/admin/system/problems`<br>`adminProxy` → `adminGet` (Bearer key), [`line 8`](../../../frontend/app/api/admin/system/problems/route.ts#L8) | `problems` [`backend/src/backend/api/system_report.py:52`](../../../backend/src/backend/api/system_report.py#L52) |
| GET `/api/admin/system/report` via `usePolling` → axios `api` client<br>[`frontend/components/admin/system-control-center.tsx:29`](../../../frontend/components/admin/system-control-center.tsx#L29) | `/api/admin/system/report`<br>[`frontend/app/api/admin/system/report/route.ts`](../../../frontend/app/api/admin/system/report/route.ts) | FastAPI GET `/admin/system/report`<br>`adminProxy` → `adminGet` (Bearer key), [`line 14`](../../../frontend/app/api/admin/system/report/route.ts#L14) | `system_report` [`backend/src/backend/api/system_report.py:20`](../../../backend/src/backend/api/system_report.py#L20) |
| GET `/api/admin/system/search` via `usePolling` → axios `api` client<br>[`frontend/components/admin/availability-control-center.tsx:19`](../../../frontend/components/admin/availability-control-center.tsx#L19) | `/api/admin/system/search`<br>[`frontend/app/api/admin/system/search/route.ts`](../../../frontend/app/api/admin/system/search/route.ts) | FastAPI GET `/admin/system/search`<br>`adminProxy` → `adminGet` (Bearer key), [`line 14`](../../../frontend/app/api/admin/system/search/route.ts#L14) | `search_report` [`backend/src/backend/api/system_report.py:38`](../../../backend/src/backend/api/system_report.py#L38) |
| GET `/api/auth/github` via link<br>[`frontend/app/admin/login/page.tsx:32`](../../../frontend/app/admin/login/page.tsx#L32) | `/api/auth/github`<br>[`frontend/app/api/auth/github/route.ts`](../../../frontend/app/api/auth/github/route.ts) | redirect GET `https://github.com/login/oauth/authorize`<br>browser redirect, [`line 12`](../../../frontend/app/api/auth/github/route.ts#L12) | external |
| POST `/api/auth/logout` via form<br>[`frontend/app/admin/(protected)/layout.tsx:22`](../../../frontend/app/admin/%28protected%29/layout.tsx#L22) | `/api/auth/logout`<br>[`frontend/app/api/auth/logout/route.ts`](../../../frontend/app/api/auth/logout/route.ts) | none (handled in Next.js) | — |
| GET `/api/search` via axios `api` client<br>[`frontend/components/search-experience.tsx:274`](../../../frontend/components/search-experience.tsx#L274) | `/api/search`<br>[`frontend/app/api/search/route.ts`](../../../frontend/app/api/search/route.ts) | FastAPI GET `/search`<br>`backend.get` on `$BACKEND_URL`, [`line 33`](../../../frontend/app/api/search/route.ts#L33) | `search` [`backend/src/backend/api/search.py:43`](../../../backend/src/backend/api/search.py#L43) |
| GET `/api/search/suggest` via axios `api` client<br>[`frontend/components/search-experience.tsx:288`](../../../frontend/components/search-experience.tsx#L288) | `/api/search/suggest`<br>[`frontend/app/api/search/suggest/route.ts`](../../../frontend/app/api/search/suggest/route.ts) | FastAPI GET `/search/suggest`<br>`backend.get` on `$BACKEND_URL`, [`line 22`](../../../frontend/app/api/search/suggest/route.ts#L22) | `suggest_search_query` [`backend/src/backend/api/search.py:94`](../../../backend/src/backend/api/search.py#L94) |

## 3. Next.js routes (`frontend/app/**/route.ts`)

| Method | Path | Auth | Reads | Upstream | File |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/admin/crawler/inspect` | viewer session | `id`, `type` | FastAPI `GET /admin/crawler/attempts/{attempt_id}`, `GET /admin/crawler/documents/{document_id}` | [`frontend/app/api/admin/crawler/inspect/route.ts`](../../../frontend/app/api/admin/crawler/inspect/route.ts) |
| GET | `/api/admin/crawler/monitor` | viewer session | `q`, `…names from a table in the file` | FastAPI `GET /admin/crawler/monitor` | [`frontend/app/api/admin/crawler/monitor/route.ts`](../../../frontend/app/api/admin/crawler/monitor/route.ts) |
| GET | `/api/admin/crawler/report` | viewer session | `…names from a table in the file` | FastAPI `GET /admin/crawler/report` | [`frontend/app/api/admin/crawler/report/route.ts`](../../../frontend/app/api/admin/crawler/report/route.ts) |
| GET | `/api/admin/indexer/report` | viewer session | `source_id` | FastAPI `GET /admin/indexer/report` | [`frontend/app/api/admin/indexer/report/route.ts`](../../../frontend/app/api/admin/indexer/report/route.ts) |
| GET | `/api/admin/indexer/vocabulary` | viewer session | `q` | FastAPI `GET /admin/indexer/vocabulary` | [`frontend/app/api/admin/indexer/vocabulary/route.ts`](../../../frontend/app/api/admin/indexer/vocabulary/route.ts) |
| GET | `/api/admin/system/corpus` | viewer session | — | FastAPI `GET /admin/system/corpus` | [`frontend/app/api/admin/system/corpus/route.ts`](../../../frontend/app/api/admin/system/corpus/route.ts) |
| GET | `/api/admin/system/hosts` | viewer session | `minutes` | FastAPI `GET /admin/system/hosts` | [`frontend/app/api/admin/system/hosts/route.ts`](../../../frontend/app/api/admin/system/hosts/route.ts) |
| GET | `/api/admin/system/problems` | viewer session | — | FastAPI `GET /admin/system/problems` | [`frontend/app/api/admin/system/problems/route.ts`](../../../frontend/app/api/admin/system/problems/route.ts) |
| GET | `/api/admin/system/report` | viewer session | `days` | FastAPI `GET /admin/system/report` | [`frontend/app/api/admin/system/report/route.ts`](../../../frontend/app/api/admin/system/report/route.ts) |
| GET | `/api/admin/system/search` | viewer session | `hours` | FastAPI `GET /admin/system/search` | [`frontend/app/api/admin/system/search/route.ts`](../../../frontend/app/api/admin/system/search/route.ts) |
| GET | `/api/auth/github` | public | — | redirect `https://github.com/login/oauth/authorize` | [`frontend/app/api/auth/github/route.ts`](../../../frontend/app/api/auth/github/route.ts) |
| GET | `/api/auth/github/callback` | public | `code`, `state` | external `https://github.com/login/oauth/access_token`<br>external `https://api.github.com/user` | [`frontend/app/api/auth/github/callback/route.ts`](../../../frontend/app/api/auth/github/callback/route.ts) |
| POST | `/api/auth/logout` | public | — | — | [`frontend/app/api/auth/logout/route.ts`](../../../frontend/app/api/auth/logout/route.ts) |
| GET | `/api/search` | public | `mode`, `page`, `q`, `source` | FastAPI `GET /search` | [`frontend/app/api/search/route.ts`](../../../frontend/app/api/search/route.ts) |
| GET | `/api/search/suggest` | public | `q` | FastAPI `GET /search/suggest` | [`frontend/app/api/search/suggest/route.ts`](../../../frontend/app/api/search/suggest/route.ts) |

## 4. FastAPI endpoints (`backend/src/backend`)

| Method | Path | Auth | Parameters | Response | Handler | Called by |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/` | none | — | `dict[str, str]` | `home` [`backend/src/backend/main.py:91`](../../../backend/src/backend/main.py#L91) | — |
| GET | `/admin/crawler/attempts/{attempt_id}` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `attempt_id` (path: int, gt=0) | — | `crawler_attempt` [`backend/src/backend/api/crawler_report.py:89`](../../../backend/src/backend/api/crawler_report.py#L89) | [`/api/admin/crawler/inspect`](../../../frontend/app/api/admin/crawler/inspect/route.ts) |
| GET | `/admin/crawler/documents/{document_id}` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `document_id` (path: int, gt=0) | — | `crawler_document` [`backend/src/backend/api/crawler_report.py:83`](../../../backend/src/backend/api/crawler_report.py#L83) | [`/api/admin/crawler/inspect`](../../../frontend/app/api/admin/crawler/inspect/route.ts) |
| GET | `/admin/crawler/monitor` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `days` (query: int, ge=1, le=365, default 7)<br>`source_id` (query: int \| None, gt=0, default None)<br>`status` (query: Literal['running', 'success', 'failed', 'blocked', 'accepted', 'skipped', 'persisted', 'not_stored', 'duplicate', 'new', 'updated', 'unchanged', 'not_modified', 'stale', 'complete'] \| None, default None)<br>`category` (query: Literal['fetch', 'parse', 'process', 'processing', 'dedup', 'store', 'discover', 'finalize', 'worker'] \| None, default None)<br>`q` (query: str, max_length=200, default '')<br>`document_page` (query: int, ge=0, le=10000, default 0)<br>`frontier_page` (query: int, ge=0, le=10000, default 0)<br>`frontier_state` (query: Literal['due', 'scheduled', 'expired', 'retry', 'queued', 'leased', 'blocked', 'disabled'] \| None, default None)<br>`before_event_id` (query: int \| None, gt=0, default None) | — | `crawler_monitor` [`backend/src/backend/api/crawler_report.py:64`](../../../backend/src/backend/api/crawler_report.py#L64) | [`/api/admin/crawler/monitor`](../../../frontend/app/api/admin/crawler/monitor/route.ts) |
| GET | `/admin/crawler/report` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `days` (query: int, ge=1, le=365, default 7)<br>`top_sources` (query: int, ge=1, le=100, default 20)<br>`recent_errors` (query: int, ge=0, le=100, default 20) | `dict` | `crawler_report` [`backend/src/backend/api/crawler_report.py:32`](../../../backend/src/backend/api/crawler_report.py#L32) | [`/api/admin/crawler/report`](../../../frontend/app/api/admin/crawler/report/route.ts) |
| GET | `/admin/indexer/report` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `source_id` (query: int \| None, gt=0, default None) | — | `indexer_report` [`backend/src/backend/api/indexer_report.py:13`](../../../backend/src/backend/api/indexer_report.py#L13) | [`/api/admin/indexer/report`](../../../frontend/app/api/admin/indexer/report/route.ts) |
| GET | `/admin/indexer/vocabulary` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `q` (query: str \| None, min_length=1, max_length=64, default None) | — | `vocabulary_report` [`backend/src/backend/api/indexer_report.py:23`](../../../backend/src/backend/api/indexer_report.py#L23) | [`/api/admin/indexer/vocabulary`](../../../frontend/app/api/admin/indexer/vocabulary/route.ts) |
| GET | `/admin/system/corpus` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | — | — | `corpus_report` [`backend/src/backend/api/system_report.py:32`](../../../backend/src/backend/api/system_report.py#L32) | [`/api/admin/system/corpus`](../../../frontend/app/api/admin/system/corpus/route.ts) |
| GET | `/admin/system/hosts` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `minutes` (query: int, ge=5, le=1440, default 60) | — | `host_report` [`backend/src/backend/api/system_report.py:26`](../../../backend/src/backend/api/system_report.py#L26) | [`/api/admin/system/hosts`](../../../frontend/app/api/admin/system/hosts/route.ts) |
| GET | `/admin/system/problems` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | — | — | `problems` [`backend/src/backend/api/system_report.py:52`](../../../backend/src/backend/api/system_report.py#L52) | [`/api/admin/system/problems`](../../../frontend/app/api/admin/system/problems/route.ts) |
| GET | `/admin/system/report` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `days` (query: int, ge=1, le=90, default 7) | — | `system_report` [`backend/src/backend/api/system_report.py:20`](../../../backend/src/backend/api/system_report.py#L20) | [`/api/admin/system/report`](../../../frontend/app/api/admin/system/report/route.ts) |
| GET | `/admin/system/search` | service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY` | `hours` (query: int, ge=1, le=168, default 24) | — | `search_report` [`backend/src/backend/api/system_report.py:38`](../../../backend/src/backend/api/system_report.py#L38) | [`/api/admin/system/search`](../../../frontend/app/api/admin/system/search/route.ts) |
| GET | `/health` | none | — | `dict[str, str]` | `health` [`backend/src/backend/main.py:96`](../../../backend/src/backend/main.py#L96) | — |
| GET | `/health/db` | none | — | `dict[str, str]` | `database_health` [`backend/src/backend/main.py:101`](../../../backend/src/backend/main.py#L101) | — |
| GET | `/search` | none | `q` (query: str, max_length=1024, required)<br>`source` (query: SearchFilter \| None, default None)<br>`limit` (query: int, ge=1, le=50, default 20)<br>`page` (query: int, ge=1, default 1)<br>`mode` (query: SearchMode, default SearchMode.ALL) | `SearchResponseOut` | `search` [`backend/src/backend/api/search.py:43`](../../../backend/src/backend/api/search.py#L43) | [`/api/search`](../../../frontend/app/api/search/route.ts) |
| GET | `/search/suggest` | none | `q` (query: str, max_length=1024, required) | `QueryCorrection` | `suggest_search_query` [`backend/src/backend/api/search.py:94`](../../../backend/src/backend/api/search.py#L94)<br>Explicit spelling suggestion from the indexer-maintained vocabulary. | [`/api/search/suggest`](../../../frontend/app/api/search/suggest/route.ts) |

## 5. Gaps found by the generator

FastAPI endpoints no Next.js route calls (reachable only inside the server, or by health checks):

- GET `/` ([`backend/src/backend/main.py:91`](../../../backend/src/backend/main.py#L91))
- GET `/health` ([`backend/src/backend/main.py:96`](../../../backend/src/backend/main.py#L96))
- GET `/health/db` ([`backend/src/backend/main.py:101`](../../../backend/src/backend/main.py#L101))

Next.js routes no browser code calls (used by other clients, redirects or OAuth):

- GET `/api/auth/github/callback` ([`frontend/app/api/auth/github/callback/route.ts`](../../../frontend/app/api/auth/github/callback/route.ts))

Broken links (calls that reach no route; `--check` fails on these):

- none

<!-- api-map:end -->
