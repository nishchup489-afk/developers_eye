# Developer’s Eye frontend

Responsive Next.js search frontend with a custom GSAP eye illustration, staggered entrances, source filters, shareable queries, browser-local saved results, keyboard shortcuts, and reduced-motion support.

## Run

```sh
npm install
npm run dev
```

Open http://localhost:3000. No environment variables are required for the labeled demo playground. It uses a small curated collection, not live third-party search.

To connect public search to FastAPI, set `BACKEND_URL=http://127.0.0.1:8000` in `.env.local` (it is on in `.env.example`), start the backend, and restart Next.js. The backend serves `GET /search` from `backend/src/backend/api/search.py` over the PostgreSQL full-text index. The crawler admin reporting endpoint is implemented separately below.

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

All HTTP calls use axios. Every axios instance lives in `lib/axios.js`: browser components call the same-origin routes through `api`, and server routes call FastAPI and GitHub through `backend`, which uses axios's fetch adapter so `cache: "no-store"`, `redirect: "error"` and request timeouts behave as before. Both clients return every status instead of throwing, so each caller maps upstream failures to its own message.

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

<!-- docs-nav:start -->
## Documentation map

Every project doc, grouped by area. Generated by `scripts/update_docs_nav.py`; edit that script, not this list.

**Start here**

- [Project overview](../README.md) `README.md`
- [Technical handoff](../technical_handoff.md) `technical_handoff.md`
- [Developers Eye — Complete Engineering Checklist](../crawler/DEVELOPERS_EYE_CHECKLIST.md) `crawler/DEVELOPERS_EYE_CHECKLIST.md`

**Tech docs (why)**

- [Tech docs index (decisions, incidents, experiments)](../0_tech_docs/README.md) `0_tech_docs/README.md`

**Backend (FastAPI, database)**

- [Developer's Eye backend](../backend/README.md) `backend/README.md`
- [Table notes: crawl_attempt](../backend/docs/db/crawl_attempt.md) `backend/docs/db/crawl_attempt.md`
- [Table notes: crawler_frontier](../backend/docs/db/crawler_frontier.md) `backend/docs/db/crawler_frontier.md`
- [Table notes: documents](../backend/docs/db/documents.md) `backend/docs/db/documents.md`
- [Table notes: robot](../backend/docs/db/robot.md) `backend/docs/db/robot.md`
- [Table notes: search_index](../backend/docs/db/search_index.md) `backend/docs/db/search_index.md`
- [Table notes: source](../backend/docs/db/source.md) `backend/docs/db/source.md`

**Crawler: seeds and frontier**

- [Crawler package](../crawler/src/crawler/README.md) `crawler/src/crawler/README.md`
- [Sitemap Discovery and Worker Jobs](../crawler/src/crawler/seed/docs/sitemap_discovery.md) `crawler/src/crawler/seed/docs/sitemap_discovery.md`
- [Seed guide](../crawler/src/crawler/seed/guide.md) `crawler/src/crawler/seed/guide.md`
- [Seed list](../crawler/src/crawler/seed/seed_list.md) `crawler/src/crawler/seed/seed_list.md`
- [Developers Eye — Source Registry Seed Plan](../crawler/src/crawler/seed/seed_listing_plan.md) `crawler/src/crawler/seed/seed_listing_plan.md`
- [Running the frontier tests](../crawler/src/crawler/frontier/tests/README.md) `crawler/src/crawler/frontier/tests/README.md`
- [Frontier test cases](../crawler/src/crawler/frontier/tests/test_case.md) `crawler/src/crawler/frontier/tests/test_case.md`
- [Scheduler repository and target states](../crawler/src/crawler/schedular/DOCS/REPOSITORY_README.md) `crawler/src/crawler/schedular/DOCS/REPOSITORY_README.md`
- [Scheduler concepts to note](../crawler/src/crawler/schedular/DOCS/new_concept_to_note.md) `crawler/src/crawler/schedular/DOCS/new_concept_to_note.md`
- [Running the scheduler tests](../crawler/src/crawler/schedular/tests/README.md) `crawler/src/crawler/schedular/tests/README.md`
- [Developers Eye — Scheduler Tests](../crawler/src/crawler/schedular/tests/test1_report.md) `crawler/src/crawler/schedular/tests/test1_report.md`
- [Schedular test cases](../crawler/src/crawler/schedular/tests/test_case.md) `crawler/src/crawler/schedular/tests/test_case.md`

**Crawler: fetch and policy**

- [Developer's Eye: Async Fetcher — Full Flow](../crawler/src/crawler/fetcher/docs/flow.md) `crawler/src/crawler/fetcher/docs/flow.md`
- [Developer's Eye fetcher tests](../crawler/src/crawler/fetcher/tests/fetcher_tests/README.md) `crawler/src/crawler/fetcher/tests/fetcher_tests/README.md`
- [Policy components overview](../crawler/src/crawler/policy_and_politeness/README.md) `crawler/src/crawler/policy_and_politeness/README.md`
- [Host Policy](../crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md) `crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md`
- [DNS/IP Policy & Safe HTTP Transport](../crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md) `crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md`
- [Robots Policy. Third step of our crawler safety checks](../crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md) `crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md`
- [Politeness Policy. Fourth step of our crawler safety checks](../crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md) `crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md`
- [Redirect Policy: What if a website sends our crawler somewhere else?](../crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md) `crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md`
- [Avengers assemble. Policy Coordinator. Final step of our crawler policy phase](../crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md) `crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md`
- [Policy docs introduction](../crawler/src/crawler/policy_and_politeness/docs/README.md) `crawler/src/crawler/policy_and_politeness/docs/README.md`
- [Running the policy and politeness tests](../crawler/src/crawler/policy_and_politeness/tests/README.md) `crawler/src/crawler/policy_and_politeness/tests/README.md`
- [Policy and politeness test cases](../crawler/src/crawler/policy_and_politeness/tests/test_case.md) `crawler/src/crawler/policy_and_politeness/tests/test_case.md`

**Crawler: parse, process, write**

- [JSON API Ingestion](../crawler/src/crawler/parser/docs/json_api.md) `crawler/src/crawler/parser/docs/json_api.md`
- [Developer's Eye: Parser Engine](../crawler/src/crawler/parser/docs/parser.md) `crawler/src/crawler/parser/docs/parser.md`
- [RSS and Atom Feed Ingestion](../crawler/src/crawler/parser/docs/rss_atom.md) `crawler/src/crawler/parser/docs/rss_atom.md`
- [XML Sitemap Parser](../crawler/src/crawler/parser/docs/sitemap.md) `crawler/src/crawler/parser/docs/sitemap.md`
- [Running the parser tests](../crawler/src/crawler/parser/tests/README.md) `crawler/src/crawler/parser/tests/README.md`
- [Parser test cases](../crawler/src/crawler/parser/tests/test_case.md) `crawler/src/crawler/parser/tests/test_case.md`
- [Classifier Model](../crawler/src/crawler/processing/docs/classifier.md) `crawler/src/crawler/processing/docs/classifier.md`
- [content processing pipeline](../crawler/src/crawler/processing/docs/content_processing.md) `crawler/src/crawler/processing/docs/content_processing.md`
- [Fingerprint Model](../crawler/src/crawler/processing/docs/fingerprint.md) `crawler/src/crawler/processing/docs/fingerprint.md`
- [Normalizer Model](../crawler/src/crawler/processing/docs/normalize.md) `crawler/src/crawler/processing/docs/normalize.md`
- [Processor Model](../crawler/src/crawler/processing/docs/processor_model.md) `crawler/src/crawler/processing/docs/processor_model.md`
- [Running the processing tests](../crawler/src/crawler/processing/tests/README.md) `crawler/src/crawler/processing/tests/README.md`
- [Processing test cases](../crawler/src/crawler/processing/tests/test_case.md) `crawler/src/crawler/processing/tests/test_case.md`
- [Developer's Eye: Database Writer](../crawler/src/crawler/writer/docs/developers_eye_writer_docs.md) `crawler/src/crawler/writer/docs/developers_eye_writer_docs.md`
- [Developer's Eye: Database Writer — Debugging & Test Report](../crawler/src/crawler/writer/tests/1st_succuessful_test_report.md) `crawler/src/crawler/writer/tests/1st_succuessful_test_report.md`

**Crawler: worker and ingestion**

- [Worker Jobs — Developer's Eye](../crawler/src/crawler/worker/docs/jobs_docs.md) `crawler/src/crawler/worker/docs/jobs_docs.md`
- [Runner.py — Developer's Eye Crawler Worker](../crawler/src/crawler/worker/docs/runner_docs.md) `crawler/src/crawler/worker/docs/runner_docs.md`
- [Running the worker tests](../crawler/src/crawler/worker/tests/README.md) `crawler/src/crawler/worker/tests/README.md`
- [Worker test cases](../crawler/src/crawler/worker/tests/test_case.md) `crawler/src/crawler/worker/tests/test_case.md`
- [Testing Crawler Ingestion](../crawler/tests/README.md) `crawler/tests/README.md`
- [Crawler test cases](../crawler/tests/test_case.md) `crawler/tests/test_case.md`

**Crawler: fix log**

- [Test run order](../crawler/src/crawler/test/order.md) `crawler/src/crawler/test/order.md`
- [Fixing PostgreSQL Deadlocks in Developer's Eye](../crawler/src/crawler/test/upadte_log/update_10_20_2026_8_39_PM.md) `crawler/src/crawler/test/upadte_log/update_10_20_2026_8_39_PM.md`
- [Fixing HTTP transport error handling](../crawler/src/crawler/test/update_log/01_transport_errors.md) `crawler/src/crawler/test/update_log/01_transport_errors.md`
- [Fixing fetcher policy rejections](../crawler/src/crawler/test/update_log/02_policy_rejections.md) `crawler/src/crawler/test/update_log/02_policy_rejections.md`
- [Fixing pinned HTTP request validation](../crawler/src/crawler/test/update_log/03_pinned_requests.md) `crawler/src/crawler/test/update_log/03_pinned_requests.md`
- [Fixing robots.txt matching](../crawler/src/crawler/test/update_log/04_robots_rules.md) `crawler/src/crawler/test/update_log/04_robots_rules.md`
- [Fixing combined robots metadata](../crawler/src/crawler/test/update_log/05_robots_metadata.md) `crawler/src/crawler/test/update_log/05_robots_metadata.md`
- [Connecting the deadlock retry helper](../crawler/src/crawler/test/update_log/06_deadlock_retry.md) `crawler/src/crawler/test/update_log/06_deadlock_retry.md`
- [Enforcing crawl depth and source budgets](../crawler/src/crawler/test/update_log/07_crawl_scope.md) `crawler/src/crawler/test/update_log/07_crawl_scope.md`
- [Fixing abandoned attempts and retry recovery](../crawler/src/crawler/test/update_log/08_failure_recovery.md) `crawler/src/crawler/test/update_log/08_failure_recovery.md`
- [Fixing stored content after 404 and 410 responses](../crawler/src/crawler/test/update_log/09_content_availability.md) `crawler/src/crawler/test/update_log/09_content_availability.md`
- [Fixing machine-specific and circular package dependencies](../crawler/src/crawler/test/update_log/10_portable_packages.md) `crawler/src/crawler/test/update_log/10_portable_packages.md`
- [Verifying the fixes against PostgreSQL](../crawler/src/crawler/test/update_log/11_postgres_regressions.md) `crawler/src/crawler/test/update_log/11_postgres_regressions.md`
- [Cleaning the frontier model whitespace](../crawler/src/crawler/test/update_log/12_frontier_whitespace.md) `crawler/src/crawler/test/update_log/12_frontier_whitespace.md`
- [Resolving the remaining merge conflicts](../crawler/src/crawler/test/update_log/13_merge_conflicts.md) `crawler/src/crawler/test/update_log/13_merge_conflicts.md`
- [Completing XML sitemap parsing](../crawler/src/crawler/test/update_log/14_sitemap_parser.md) `crawler/src/crawler/test/update_log/14_sitemap_parser.md`
- [Wiring sitemap discovery into the worker](../crawler/src/crawler/test/update_log/15_sitemap_discovery.md) `crawler/src/crawler/test/update_log/15_sitemap_discovery.md`
- [Adding RSS and Atom ingestion](../crawler/src/crawler/test/update_log/16_rss_atom_ingestion.md) `crawler/src/crawler/test/update_log/16_rss_atom_ingestion.md`
- [Adding configurable JSON API ingestion](../crawler/src/crawler/test/update_log/17_json_api_ingestion.md) `crawler/src/crawler/test/update_log/17_json_api_ingestion.md`
- [Closing structured-ingestion edge cases and verifying persistence](../crawler/src/crawler/test/update_log/18_structured_ingestion_edges.md) `crawler/src/crawler/test/update_log/18_structured_ingestion_edges.md`
- [Reconciling the local and remote ingestion histories](../crawler/src/crawler/test/update_log/19_ingestion_history_merge.md) `crawler/src/crawler/test/update_log/19_ingestion_history_merge.md`

**Indexer**

- [Developer's Eye indexer service + writer](../crawler/src/indexer/README.md) `crawler/src/indexer/README.md`
- [Developer's Eye: Indexer Analyzer](../crawler/src/indexer/docs/ANALYZER.md) `crawler/src/indexer/docs/ANALYZER.md`
- [Developer's Eye — Indexer: Builder](../crawler/src/indexer/docs/builder.md) `crawler/src/indexer/docs/builder.md`
- [Indexer configuration](../crawler/src/indexer/docs/config.md) `crawler/src/indexer/docs/config.md`
- [Indexer file responsibilities](../crawler/src/indexer/docs/file_task.md) `crawler/src/indexer/docs/file_task.md`
- [reporting.py — indexer coverage report](../crawler/src/indexer/docs/reporting.md) `crawler/src/indexer/docs/reporting.md`
- [Developer's Eye — Indexer: Selector](../crawler/src/indexer/docs/selector.md) `crawler/src/indexer/docs/selector.md`
- [Developer's Eye: Indexer service](../crawler/src/indexer/docs/service.md) `crawler/src/indexer/docs/service.md`
- [Developer's Eye: vector.py](../crawler/src/indexer/docs/vector.md) `crawler/src/indexer/docs/vector.md`
- [Developer's Eye: Transactional index writer](../crawler/src/indexer/docs/writer.md) `crawler/src/indexer/docs/writer.md`
- [Developer's Eye indexer operations](../crawler/src/indexer/operations.md) `crawler/src/indexer/operations.md`
- [Running the indexer tests](../crawler/src/indexer/tests/README.md) `crawler/src/indexer/tests/README.md`
- [Indexer test cases](../crawler/src/indexer/tests/test_case.md) `crawler/src/indexer/tests/test_case.md`

**Frontend (Next.js, admin)**

- [Developer’s Eye frontend](README.md) `frontend/README.md` (you are here)
- [Developer’s Eye — API and backend connector reference](public/api-reference.md) `frontend/public/api-reference.md`
- [Running the frontend tests](tests/README.md) `frontend/tests/README.md`
- [Frontend test cases](tests/test_case.md) `frontend/tests/test_case.md`

**Other**

- [Faced problems](../crawler/faced_problems.md) `crawler/faced_problems.md`
<!-- docs-nav:end -->
