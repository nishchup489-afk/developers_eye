# Frontend test cases

Node test scripts for the Next.js frontend, using `node:assert/strict` (no test framework). Each script prints `PASS ...` lines and throws on the first failed assertion. The integration scripts need a production build (`next build`) because they run `next start`.

| Script | npm command |
| --- | --- |
| `integration.mjs` | `npm run test:integration` |
| `admin-integration.mjs` | `npm run test:admin` |
| `admin-unit.mjs`, `crawler-monitor-unit.mjs`, `indexer-report-unit.mjs`, `search-quality-unit.mjs` | `npm run test:admin:unit` |
| `admin-routes.mjs` | `npm run test:admin:routes` |
| `search-unit.mjs`, `knowledge-unit.mjs` | `npm run test:search:unit` |
| `preview-crawler.mjs` | Run manually; it is a preview server, not a test. |

## fixtures/

Synthetic data used only by tests:

- `crawler-report.mjs`: `fixture(days)` builds a valid crawler report (sources, frontier, documents, robots cache, attempts, one row per day, top sources, recent errors) for a given day window.
- `crawler-monitor.mjs`: `monitorFixture()`, `documentFixture()`, and `attemptFixture()` build a valid crawl monitor snapshot, document detail, and attempt detail with a full FETCH to FINALIZE event trail.
- `search-quality.mjs`: `slowFixture()`, `evaluationFixture()`, and `judgingFixture()` build a slow-search report (one timeout in ranking), an evaluation report (one complete and one unpooled query), and a judging query with a pooled and a hand-added page.

## integration.mjs

Starts the built app twice with `next start`: once with no `BACKEND_URL` (demo mode, port 3181) and once pointed at a local mock search backend (live mode, port 3182). Both point `WIKIPEDIA_API_URL` at a mock MediaWiki action API on the same mock server, so no test reaches Wikipedia.

| Area | What it checks |
| --- | --- |
| Pages and routing | The home page has the eye art and sources section but no results; `/search?q=react` shows results with the query filled in and no home sections; `/search` loads; `/search?saved=1` shows the personal index page; the legacy `/?q=...&source=...` URL redirects (307) to `/search`. |
| Demo search API | `/api/search` trims the query, returns `mode: demo` with results, filters by `source`, returns an empty list for nonsense, and always sends `Cache-Control: no-store`. Missing, blank, over 300 character queries and unknown sources return 400; `POST` returns 405. `/docs` loads and `/api-reference.md` contains the provider connectors section. |
| Live proxy | Returns `mode: live` with the upstream result. Upstream 503, malformed JSON, a `javascript:` URL, an empty-host URL, an unknown source, and non-string tags all return 502 with an `error` and no `results`. A hung upstream returns 504, and a closed upstream returns 502. There is no fallback to demo data. |
| Demo suggestions | `/api/search/suggest` returns `suggestion: null` with `mode: demo` (no vocabulary in demo mode); missing and over 300 character queries return 400. |
| Knowledge panel | `/api/search/knowledge` trims the query and returns the redirect target for `postgres` (PostgreSQL, with its Wikimedia thumbnail). A second lookup (`Postgres`) is served from the in-memory cache without calling the mock again. `rust` returns the programming language over the iron-oxide article, `python` skips the disambiguation page for the programming language, and `apple` keeps the exact article. A fuzzy-only hit (`react hooks tutorial`), an unsafe article URL and malformed JSON give `panel: null`; pasted code gives `panel: null` without calling Wikipedia. Answers carry `Cache-Control: public, max-age=3600`. Upstream 503 returns 502 and a hung upstream 504 (4 s deadline), both `no-store`; missing and over 300 character queries return 400. |
| Live suggestions | `/api/search/suggest` forwards to FastAPI `/search/suggest`: `pyhton   async` returns `python async` with only `original`/`replacement` in `corrections`. An unchanged suggestion, an upstream 422 and pasted multi-line code return `suggestion: null`. Upstream 503, malformed JSON and a schema-invalid body return 502, a hung upstream 504 (5 s deadline, also on the server's first request), and a closed upstream 502. |

## admin-integration.mjs

Starts the built app with admin settings and a mock crawler report service, then calls it over HTTP. Session cookies are signed locally with the test secret.

| Area | What it checks |
| --- | --- |
| Protected pages | `/admin` and `/admin/crawler` redirect (307) to `/admin/login` without a session, and the login page shows "Continue with GitHub". |
| Session rejection | `/api/admin/crawler/report` returns 401 with `Cache-Control: private, no-store` for no cookie, a forged cookie, a non-allowlisted GitHub ID, an expired session, a wrong-purpose (`oauth`) token, and a tampered signature. The upstream is never called. |
| OAuth start | `/api/auth/github` redirects to GitHub with PKCE `S256`, the correct callback URL, 43-character state and challenge, and an `HttpOnly` flow cookie. A callback with the wrong state redirects with `error=state` and clears the flow cookie. |
| Authenticated report | With a valid session, `/admin/crawler` renders, and the report proxy returns 7, 30, and 90 day windows with one row per day. `days=0`, `days=366`, `days=7oops`, `top_sources=101`, and `recent_errors=-1` return 400. |
| Upstream failures | Upstream 503, 401, an invalid report shape, and broken JSON all return 502 with an `error` string. |
| Logout | A cross-origin `POST /api/auth/logout` returns 403; a same-origin one returns 303 and clears the session cookie. |

## admin-routes.mjs

Calls the compiled production route handlers directly from `.next` (or `NEXT_BUILD_DIR`) inside Next's request context, with `fetch` mocked, so no sockets are opened.

| Area | What it checks |
| --- | --- |
| Report auth | No cookie, a forged or tampered token, an expired session, a non-allowlisted ID, and an `oauth`-purpose token all return 401 without calling the upstream. |
| Monitor and inspect routes | Both return 401 without a valid session, and 200 with `Cache-Control: private, no-store` and `Vary: Cookie` with one. The monitor forwards only allowlisted query parameters (an `unknown` parameter is dropped). Invalid `days`, `source_id`, `status`, `category`, `frontier_page`, and an over 200 character `q` return 400. The inspector rejects an unknown `type`, `id=0`, and a path-traversal ID with 400. Upstream malformed and unavailable responses give 502, a timeout 504, and not found 404. |
| Report handler | A valid request forwards the service key and query (including `recent_errors=0`) and returns `private, no-store`. Out-of-range or malformed queries return 400; upstream unavailable or malformed gives 502 and a timeout 504; a missing `CRAWLER_REPORT_API_KEY` gives 503. |
| OAuth handlers | Initiation uses PKCE `S256` and seals the state in the flow cookie. A wrong state is rejected before any token exchange. A good callback exchanges the code (sending the client secret and code verifier), loads the GitHub user, redirects to `/admin/crawler`, sets a signed session that does not contain the access token, and clears the flow cookie. A GitHub user not on the allowlist gets `error=denied` and no session. |
| Logout handler | A cross-origin logout returns 403; same-origin returns 303 and clears every cookie. |

| Read-only access | A listed viewer (`ADMIN_VIEWER_GITHUB_IDS`) signs in through the OAuth callback, is not an administrator, and reads the crawler monitor, crawler report, system report, hosts and problems routes (200, `private, no-store`). The system report's `slow_queries` is `null` for viewers and guests and present for admins. `days` outside 1–90 and `minutes` outside 5–1440 return 400; no session returns 401; a malformed upstream returns 502. With `ADMIN_VIEWER_ACCESS=public` a request with no cookie reads reports; switching back to `off` and clearing viewer ids revokes the viewer at once. |
| Search quality routes | Slow searches show query text to admins and `(hidden)` / `Query N` to viewers; `hours` outside 1–720 and `limit` outside 1–500 return 400; evaluation `k` other than 5 or 10 returns 400; a query id that is not 1–32 letters, digits, `-` or `_` returns 400. Judgment, query, pool and import writes return 401 for viewers and guests and 403 from another origin, and a bad grade or mode returns 400, all without calling the backend. An admin write forwards the checked body with `judge` set to the session login (a client-sent `judge` is replaced); backend 422 detail is passed through and 404 stays 404. Deleting an added page forwards its URL and rejects a non-http(s) URL. |

## admin-unit.mjs

Unit tests for `lib/admin-session.ts` and `lib/crawler-report.ts`, run with `--experimental-strip-types`.

| Area | What it checks |
| --- | --- |
| Session signing | A sealed session round-trips to the identity. Missing, tampered, re-signed, expired, wrong-purpose, non-allowlisted, unsafe-login (`<script>`), and string-ID sessions return `null`. OAuth flow tokens only unseal with the `oauth` purpose. Removing an ID from `ADMIN_GITHUB_IDS` revokes its session. |
| Fail-closed config | An empty allowlist or a plain `http://` public app URL makes `adminConfig()` not ready. A short session secret rejects existing tokens and makes `seal` throw. |
| Cookie flags | Cookies are `Secure`, `HttpOnly`, and `SameSite=Lax` on an HTTPS app URL. |
| Report contract | `isCrawlerReport` accepts 7, 30, and 90 day fixtures and null metrics when there are no samples, and rejects a missing section, negative counts, a success rate over 100, an empty `by_state`, a date-only timestamp, a missing day, a non-boolean `enabled`, and an HTTP status of 900. |
| Safe links | `safeHttpUrl` rejects `javascript:`, `data:`, credentialed, host-less, and relative URLs, and accepts a normal https URL. |
| Read-only roles | `viewerFromSession` returns `admin` for admin ids, `viewer` for `ADMIN_VIEWER_GITHUB_IDS` or any valid identity with `ADMIN_VIEWER_ACCESS=github`, and an anonymous `guest` only with `public`. `userFromSession` never accepts a viewer, unknown access modes fall back to `off`, and removing a viewer id revokes the session. |
| System report contracts | `isSystemReport`, `isHostReport` and `isProblemsReport` accept the fixtures and reject an unknown budget status, negative sizes, a percent over 100, missing telemetry, unknown host flags and unknown severities. Null projections (no documents yet) are valid. Viewer and guest redaction drops `slow_queries`. `bytes()` and `eta()` format sizes and long ETAs. |

## crawler-monitor-unit.mjs

Unit tests for the validators in `lib/crawler-monitor.ts`.

| Area | What it checks |
| --- | --- |
| Valid fixtures | `isCrawlMonitor`, `isDocumentDetail`, and `isAttemptDetail` accept the fixtures. |
| Malformed monitor data | A string latency, negative persisted count, `null` event details, a numeric worker URL, a short throughput series, a string `documents_has_more`, and an invalid `next_fetch_at` are rejected. |
| Empty monitor | Null metrics and empty workers, events, documents, and frontier lists are accepted. |
| Details | A document whose `latest_attempt` has a bad ID and an attempt with array telemetry are rejected. An unavailable document with numeric `unavailable_http_status` (410) is accepted, but a string status is rejected. |

## indexer-report-unit.mjs

Unit test for the validator in `lib/indexer-report.ts`, behind the `/admin/indexer` page.

| Area | What it checks |
| --- | --- |
| Valid report | `isIndexerReport` accepts a full report: coverage, activity, a 60-point throughput series, recent, pending and per-source rows. |
| Malformed reports | A wrong `version`, a negative pending count, coverage over 100%, an unknown activity status, a 59-point throughput series, an unknown pending reason, a non-boolean `current` and an invalid timestamp are each rejected. |
| Empty index | Null coverage and timestamps, status `empty`, and empty recent, pending and source lists are accepted. |

## search-unit.mjs

Unit test for the spelling-suggestion helpers in `lib/search.ts`, behind the "Did you mean" line on the results page.

| Area | What it checks |
| --- | --- |
| When to ask | `shouldSuggest` is true only below 3 results, for non-blank single-line queries of at most 256 characters with a plain word of 4+ letters. |
| Valid payload | `parseCorrection` returns the collapsed suggested query and `{original, replacement}` corrections. |
| Nothing to suggest | A suggestion equal to the query (ignoring case and spacing), an empty one, or one without corrections becomes `suggestion: null`. |
| Malformed payloads | Non-objects, a non-string `suggested_query`, non-array `corrections` and incomplete correction items return null. |

## knowledge-unit.mjs

Unit test for the Wikipedia knowledge-panel helpers in `lib/knowledge.ts`, behind the panel beside the results.

| Area | What it checks |
| --- | --- |
| Which queries | `knowledgeQuery` collapses spacing and accepts short topics like `C++`; pasted code, under 2 or over 60 characters, more than five words, no letters and code punctuation return null. |
| Confident matches | `pickPanel` returns an exact title or redirect target that is a real article; a computing search hit (`Rust (programming language)`) beats an exact article that is not about computing, but not one that is (`Redis`); a disambiguation page falls through to the best-ranked computing match; a non-computing exact article (`Apple`) still shows when nothing better exists. |
| No panel | A fuzzy search hit, only a disambiguation page, a "may refer to" stub, a "List of" page, a non-article namespace, a `javascript:` or non-Wikipedia URL and a malformed body return null. |
| Thumbnails and text | Thumbnails are kept only from `upload.wikimedia.org` with positive dimensions; `trimExtract` cuts at a sentence boundary or adds an ellipsis. |
| Browser validation | `isKnowledgeResponse` accepts `panel: null` and a valid panel and rejects malformed bodies and unsafe URLs. |

## search-quality-unit.mjs

| Area | What it checks |
| --- | --- |
| Contract | `isSlowSearchReport`, `isEvaluationReport` and `isJudgingQuery` accept the fixtures and an empty window whose stage means are all null, and reject a non-numeric time, a string stage mean, a missing list, `k=7`, a string metric, a grade of 4 and an unknown origin. |
| Redaction | `redactSlowSearchReport` keeps query text for admins and hides it for viewers and guests while keeping the timings. |
| Write bodies | `judgmentBody` keeps only `url`, `grade`, `note` and `add`, and rejects non-http(s) URLs, grades outside 0–3 or not integers, notes over 2,000 characters and URLs over 2,048. `queryBody` trims the query and rejects an empty or over 256 character query, an unknown mode and wrong field types. |

## preview-crawler.mjs

Not an automated test. It starts a mock crawler API (port 3458), the app from `.next-crawler-monitor` (port 3459), and a proxy (port 3457). Opening `http://127.0.0.1:3457/__test_session` sets a signed test admin session and redirects to `/admin/crawler`, so the dashboard can be viewed with fixture data. It stops on Ctrl+C.
