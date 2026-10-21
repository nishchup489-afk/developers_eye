# Developer’s Eye frontend

Responsive Next.js search frontend with a custom GSAP eye illustration, staggered entrances, source filters, shareable queries, browser-local saved results, keyboard shortcuts, and reduced-motion support.

## Run

```sh
npm install
npm run dev
```

Open http://localhost:3000. No environment variables are required for the labeled demo playground. It uses a small curated collection, not live third-party search.

To connect public search to FastAPI, copy `.env.example` to `.env.local`, set `BACKEND_URL=http://127.0.0.1:8000`, and restart. The backend must implement the documented GET /search contract. The crawler admin reporting endpoint is implemented separately below.

## Checks

```sh
npm run lint
npm run build
npm run test:integration
```

Integration checks require the production build and start isolated local Next.js servers plus a mock upstream. No actual backend or provider credentials are used.

## Documentation

Visit `/docs` for the API overview or read [the full API and connector reference](public/api-reference.md). It distinguishes implemented frontend endpoints from all proposed public/admin backend routes and provider connector contracts.

## Architecture

`app/page.tsx` passes server configuration mode to the interactive search component. The browser calls same-origin `/api/search`; the route reads BACKEND_URL and forwards validated searches server-side. No provider credentials are exposed. Failed live requests return errors rather than demo results.

Public search does not require an account. Saved items live in this browser's localStorage. Query suggestions are static shortcuts. Source tabs filter the received result collection. The separate `/admin` workspace requires GitHub authentication and an explicit administrator allowlist.

The landing page centers the animated eye illustration, wordmark, and rounded search field in a full-height first screen. The source cards begin below the viewport on desktop and mobile, accessible by scrolling or the sources navigation link. Searches and suggestions open `/search?q=...`; source cards also pass a `source` filter. Results have a compact search field, source filters, and bookmarks, without the landing hero or source cards. Saved items open `/search?saved=1`. Query URLs support refresh and browser history; legacy `/?q=...` links redirect to the results page. The eye illustration lives in `components/brand-eye.tsx` as a reusable brand asset. The four source cards are Docs, GitHub, Discussions, and Articles; Discussions groups Stack Overflow and Reddit locally while preserving their separate API source values. Bookmarks remain local to this browser.

## Admin and crawler reporting

Open `/admin` to sign in. `/admin/crawler` opens on stored documents: search titles or canonical URLs, then select a document to inspect its actual extracted body, description, word count, metadata, content hash, and matching content at other URLs. Open its latest crawl attempt to inspect redirects, HTTP status, processing decisions, skips, failures, and stored document references. Raw HTML is not retained.

The other tabs show live pipeline events, current URL tasks, frontier states and retries, source health, worker heartbeats, throughput, latency, and a pipeline funnel. Events and documents refresh every five seconds while visible; database totals refresh every 30 seconds. Refresh can be paused and snapshots exported as JSON. Date ranges use UTC calendar days including today; document browsing shows current database content across all time. Older attempts remain visible without invented stage measurements. Missing connections produce an error, never fixture analytics. No start/stop or destructive crawler controls are exposed.

Before using the updated worker and dashboard, apply the additive observability migration from the repository root:

```powershell
$env:PYTHONPATH = "$(Resolve-Path .\crawler\src);$(Resolve-Path .\backend\src)"
.\crawler\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

Restart the backend and worker afterward. The migration adds attempt measurements, stage events, heartbeats, and lookup indexes; existing crawler documents are retained. The new backend endpoints are `GET /admin/crawler/monitor`, `GET /admin/crawler/documents/{id}`, and `GET /admin/crawler/attempts/{id}`. They require the same reporting key and are accessed through authenticated frontend proxy routes.

### GitHub setup

1. Copy `.env.example` to `.env.local` if you have not already created it.
2. Create a GitHub OAuth App at https://github.com/settings/developers. For local development, use homepage `http://localhost:3000` and callback **`http://localhost:3000/api/auth/github/callback`**. Match the host exactly when browsing; `localhost` and `127.0.0.1` have different cookies.
3. Set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `ADMIN_APP_URL` in `.env.local`.
4. Set `ADMIN_GITHUB_IDS` to your numeric GitHub account ID. You can look it up using `https://api.github.com/users/YOUR_USERNAME`. Multiple IDs are comma-separated. An empty list denies everyone, and the allowlist is rechecked on every protected request.
5. Generate `ADMIN_SESSION_SECRET` using `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`. Generate a separate `CRAWLER_REPORT_API_KEY`, and set that same reporting key in `backend/.env`. All variables are server-only. Never prefix them with `NEXT_PUBLIC_`.
6. Set `CRAWLER_REPORT_API_URL=http://127.0.0.1:8000/admin/crawler/report`, then restart the frontend.

GitHub OAuth uses state verification and S256 PKCE. Only the verified public user identity enters a signed, HttpOnly, SameSite cookie with an eight-hour expiry. GitHub access tokens are never stored in browser storage or session cookies. The session signing secret must be at least 32 characters. Production `ADMIN_APP_URL` must use HTTPS. Use separate OAuth Apps and secrets for local and production environments. Removing an ID from the allowlist and restarting immediately denies its existing sessions; rotating the session secret invalidates all sessions.

### Start the reporting backend (PowerShell, repository root)

The backend HTTP adapter requires the crawler package in its Python import path. It wraps the existing report builder without modifying `reporting.py` or dispatching work. Use the crawler environment, which already includes the backend and asyncpg dependencies:

```powershell
$env:PYTHONPATH = "$(Resolve-Path .\crawler\src);$(Resolve-Path .\backend\src)"
.\crawler\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Set your existing database URL and `CRAWLER_REPORT_API_KEY` in `backend/.env`. The database must already have the project's migrations. The adapter serves `GET /admin/crawler/report?days=7&top_sources=20&recent_errors=20`, requiring `Authorization: Bearer YOUR_REPORT_KEY`. Limits are days 1–365, sources 1–100, and recent errors 0–100. Browser requests go through `/api/admin/crawler/report`, which verifies the admin session before forwarding the service key. Backend errors and malformed snapshots are handled explicitly; reports are not cached.

### Admin validation

```sh
npm run lint
npm run build
npm run test:admin
npm run test:admin:unit
npm run test:admin:routes
```

The unit suite checks session signing, expiry, allowlist revocation, cookie flags, report schema validation, and safe links without networking. It requires Node 22.18+ or Node 24 for TypeScript stripping. The route suite invokes the built production handlers in a Next.js request context with mocked fetch, including a complete simulated GitHub code exchange and identity check. It requires a production build first. The HTTP integration suite starts isolated local servers with temporary test credentials and an HTTP report fixture. It verifies login redirects, signed-session enforcement, expiry, allowlist checks, state/PKCE initiation, invalid callbacks, logout origin checks, query limits, upstream credential forwarding, malformed reports, and report failures. These tests never sign in to a real GitHub account. Complete one real OAuth login with your configured GitHub App before deploying.

For an isolated build alongside an existing development server, set `NEXT_BUILD_DIR=.next-admin-verify` for both the build and tests. If Turbopack cannot spawn its worker in your execution environment, run `npm run build -- --webpack`.
