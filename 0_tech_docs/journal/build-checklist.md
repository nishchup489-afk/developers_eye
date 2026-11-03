# Developers Eye — Complete Engineering Checklist

**Project:** Developers Eye, a developer-focused search engine  
**Architecture:** Next.js frontend + FastAPI backend + independent Python/asyncio crawler and indexer + PostgreSQL  
**Status reference:** October 8, 2026  
**Principle:** Complete one end-to-end search vertical slice before building distributed infrastructure.

**Labels:** `MVP` = required for an initial usable search engine; `HARDEN` = needed before a reliable public launch; `LATER` = defer until measured demand.  
**Status:** `[x]` indicates a scaffold or file visibly present in the supplied file tree, **not** verified working behavior.

## 0. Repository and architecture — MVP
- [x] Create `developers-eye/` repository root.
- [x] Scaffold `frontend/` as a Next.js application.
- [x] Scaffold `backend/` as a Python/Poetry package.
- [x] Create initial `README.md` and `system_design.md`.
- [ ] Move the empty `backend/crawler/` to root-level `crawler/`.
- [ ] Initialize `crawler/` as a standalone Poetry package with a `src/crawler/` package.
- [ ] Add `backend/src/backend/main.py` for FastAPI and `crawler/src/crawler/main.py` for the worker.
- [ ] Document the role and process model of `frontend/`, `backend/`, and `crawler/`.
- [ ] Keep `indexer/` inside `crawler/` at first; separate it only when necessary.
- [ ] Agree on the normalized document contract shared by crawler and backend.
- [ ] Add project-root `.gitignore` for `frontend/.npm-cache/`, `node_modules`, `.next`, `.venv`, `__pycache__`, and secrets.
- [ ] Add `.env.example` for each application, without credentials.
- [ ] Choose consistent formatting, linting, typing, and test commands.
- [ ] Add root `compose.yaml` for local PostgreSQL and services.
- [ ] Create a concise architecture decision log for important tradeoffs.

**Exit gate:** All three applications can be started independently and the repository contains no generated caches or secrets.

## 1. Define the product and MVP corpus — MVP
- [ ] Write one sentence describing who Developers Eye serves and why it beats generic web search for that task.
- [ ] Define the first 3–5 query use cases (e.g., Python async documentation, open GitHub issues, troubleshooting).
- [ ] Choose only two source categories for MVP: public technical documentation and GitHub issues.
- [ ] Choose an initial allowlisted set of documentation sites.
- [ ] Record each source's ingestion method (HTML, sitemap, RSS, or official API), permissions, and retention rules.
- [ ] Define searchable document types: `documentation`, `github_issue` first.
- [ ] Define required result fields: title, URL, source, type, snippet, updated/fetched date.
- [ ] Decide which features are explicitly out of MVP: accounts, AI answers, personalized feeds, massive-scale crawling.
- [ ] Establish a small, manually curated relevance-evaluation set of at least 30 real search queries.

**Exit gate:** A bounded corpus, feature scope, and objective quality test exist before expansion.

## 2. First end-to-end search vertical slice — MVP
- [ ] Start local PostgreSQL and create initial migrations.
- [ ] Define `sources`, `url_frontier`, and `documents` tables.
- [ ] Implement normalized URL handling and a unique URL key.
- [ ] Fetch one explicitly allowlisted documentation source safely with `httpx.AsyncClient`.
- [ ] Respect `robots.txt` and a conservative per-host request interval.
- [ ] Parse HTML with BeautifulSoup + `lxml`.
- [ ] Extract document title, canonical URL, headings, and cleaned main text.
- [ ] Discover allowed hyperlinks and follow a bounded number of pages.
- [ ] Save 50 distinct valid documents; deduplicate reruns.
- [ ] Add a weighted PostgreSQL `tsvector` full-text index with a GIN index.
- [ ] Create FastAPI `GET /search?q=...` using a safely constructed full-text query.
- [ ] Render real database-backed results in the existing Next.js search page.
- [ ] Add loading, empty-result, network-error, and result-detail states.
- [ ] Confirm a query retrieves a relevant crawled page without external live search calls.

**Exit gate:** Seed URL → crawl → extracted document → PostgreSQL index → FastAPI → Next.js search results.

## 3. Source registry and URL discovery — MVP → HARDEN
- [ ] Create `source_registry` configuration schema (ID, domain, type, allowed paths, max depth, priority, enabled).
- [ ] Store durable source configuration in PostgreSQL; optionally seed it from YAML.
- [ ] Add commands to register, list, enable, disable, and inspect sources.
- [ ] Implement manual seed ingestion.
- [ ] Implement sitemap discovery from `robots.txt` and known `sitemap.xml` URLs.
- [ ] Parse sitemap indexes and nested XML sitemaps with size/entry limits.
- [ ] Support RSS/Atom feed discovery for approved sources.
- [ ] Extract and resolve relative links with `urljoin`.
- [ ] Remove URL fragments and normalize scheme/host/path/query conservatively.
- [ ] Exclude `mailto:`, `javascript:`, `tel:`, `data:`, and unsupported protocols.
- [ ] Reject URLs outside the registered source scope.
- [ ] Detect calendar traps, session IDs, search result loops, and query explosions.
- [ ] Enforce maximum discovery depth and URLs-per-source budgets.
- [ ] Track discovery origin and source attribution for each URL.

**Exit gate:** Adding one approved source leads to bounded, duplicate-free URL discovery.

## 4. Frontier, scheduling, and worker lifecycle — HARDEN
- [ ] Design frontier fields: URL, source, priority, status, attempts, next-fetch timestamp, lease owner, lease expiry.
- [ ] Implement atomic job claiming in PostgreSQL (`FOR UPDATE SKIP LOCKED`).
- [ ] Implement lease renewal and recovery of expired leases.
- [ ] Implement clear states: pending, leased, succeeded, retry_wait, blocked, failed.
- [ ] Implement idempotent inserts for discovered URLs.
- [ ] Implement priority ordering while respecting host cooldowns.
- [ ] Implement bounded global concurrency and per-host concurrency.
- [ ] Implement per-source crawl budgets and pause/resume controls.
- [ ] Schedule recrawls according to source policy and observed change rates.
- [ ] Delay retryable failures with exponential backoff and jitter.
- [ ] Honor server `Retry-After` guidance.
- [ ] Set an upper bound on retry attempts; store permanent failures separately.
- [ ] Preserve frontier state across restarts and forced worker termination.
- [ ] Add graceful shutdown that stops claiming new work and releases/completes in-flight jobs safely.
- [ ] Test two workers claiming jobs concurrently without processing the same lease.

**Exit gate:** Workers can run indefinitely, recover after crashes, and avoid duplicate leasing.

## 5. Fetch engine, safety, and politeness — HARDEN
- [ ] Use a long-lived pooled `httpx.AsyncClient` with explicit timeouts and connection limits.
- [ ] Identify the crawler with an appropriate User-Agent and contact URL/email.
- [ ] Implement RFC 9309 robots rules and a robots cache with expiration.
- [ ] Treat temporarily unreachable robots files conservatively; distinguish them from unavailable 4xx files.
- [ ] Implement host-specific cooldowns and request throttling.
- [ ] Enforce a strict outbound URL safety policy against localhost, private, loopback, link-local, and other forbidden destinations.
- [ ] Revalidate every redirected destination and resolved IP against the outbound network policy.
- [ ] Limit redirect count, response bytes, decompressed bytes, and request duration.
- [ ] Allow only intended content types (initially HTML and configured feeds/API JSON).
- [ ] Handle 200, 301/302, 304, 400, 403, 404, 410, 429, and 5xx differently.
- [ ] Implement conditional fetches with ETag and Last-Modified.
- [ ] Avoid unnecessary re-downloads on `304 Not Modified`.
- [ ] Record fetch metadata: final URL, HTTP status, duration, bytes, source ID, and error classification.
- [ ] Keep provider credentials in environment variables or secret management.
- [ ] Never implement CAPTCHAs, login-wall circumvention, or anti-bot evasion.
- [ ] Check source terms/permissions and takedown procedures.

**Exit gate:** Network failures, hostile URLs, and slow websites cannot make the crawler unsafe or unstable.

## 6. Parsing and content processing — MVP → HARDEN
- [ ] Extract metadata: title, description, canonical URL, headings, language, published/modified time when available.
- [ ] Remove scripts, styles, navigation, cookie banners, and repeated boilerplate from main text.
- [ ] Preserve useful technical content such as code blocks and heading hierarchy.
- [ ] Implement generic article/documentation extraction.
- [ ] Add source-specific extraction adapters where generic extraction is inaccurate.
- [ ] Define a normalized `Document` schema with `id`, `source_id`, `url`, `canonical_url`, `type`, `title`, `text`, `metadata`, timestamps.
- [ ] Validate documents; reject empty, exceptionally short, binary, or malformed content.
- [ ] Deduplicate by canonical URL and normalized content hash.
- [ ] Keep content-update timestamps and track whether a document actually changed.
- [ ] Record outgoing links and anchor text if useful for discovery and ranking.
- [ ] Store raw HTML only when justified, within a retention and cost policy.
- [ ] Support tombstoning/removing records for deleted pages and takedown requests.
- [ ] Respect applicable indexing directives such as `noindex` and source-specific API rules.

**Exit gate:** Documents retain readable content and reliable metadata across different page templates.

## 7. Additional developer data connectors — MVP → LATER
- [ ] Build an authenticated GitHub REST API connector for selected repositories/issues.
- [ ] Support GitHub pagination and durable synchronization cursors.
- [ ] Ingest issue title, body, labels, state, repository, creation/update timestamps, and URL.
- [ ] Obey GitHub primary/secondary rate limits and conditional-request guidance.
- [ ] Support incremental sync rather than repeatedly fetching every issue.
- [ ] Normalize GitHub issues into the shared document contract.
- [ ] Add official API/RSS ingestion of technical discussions where permitted. (LATER)
- [ ] Add Stack Overflow/Stack Exchange connector using its supported API and rules. (LATER)
- [ ] Add registered engineering blogs and changelogs. (LATER)
- [ ] Add developer-event feeds and normalize location, date/time zone, and event URLs. (LATER)
- [ ] Add geographic event filtering without requiring user location to be stored. (LATER)
- [ ] Add conference/hackathon sources with explicit refresh/expiry policies. (LATER)

**Exit gate:** More sources can be added via adapters without rewriting the scheduler or search API.

## 8. Indexing, search retrieval, and ranking — MVP → HARDEN
- [ ] Keep search indexing behind a clear `indexer/` interface within the crawler package.
- [ ] Add a transactional outbox or durable `index_jobs` table so changes are never silently lost.
- [ ] Implement idempotent upsert and deletion handling for indexed documents.
- [ ] Build weighted PostgreSQL FTS: title > headings/tags > body.
- [ ] Create GIN index and verify query plans for representative searches.
- [ ] Use `websearch_to_tsquery` (or other safely parameterized query builder) for user input.
- [ ] Build retrieval filters for source, document type, and time range.
- [ ] Add a basic relevance score combining lexical match with lightweight freshness/source-quality signals.
- [ ] Avoid boosting recent but irrelevant pages above strong lexical matches.
- [ ] Generate readable, HTML-escaped highlighted snippets.
- [ ] Implement stable pagination and deterministic tie-breaking.
- [ ] Remove duplicate canonical URLs from result sets.
- [ ] Decide how to handle reindexing, deletes, and schema migrations.
- [ ] Provide an admin-only reindex command and index-health metrics.
- [ ] Measure relevance against the curated query set and save baseline results.
- [ ] Add synonyms, typo tolerance, or trigram suggestions only after measuring need. (LATER)
- [ ] Consider BM25/OpenSearch when PostgreSQL FTS becomes a measured bottleneck. (LATER)
- [ ] Consider embeddings/hybrid retrieval and optional reranking after a strong lexical baseline. (LATER)

**Exit gate:** Users receive relevant and explainable results with bounded latency and filter support.

## 9. FastAPI online backend — MVP → HARDEN
- [ ] Establish `backend/src/backend/main.py` and routers for public endpoints.
- [ ] Implement `GET /health` and `GET /ready`.
- [ ] Implement `GET /search` with query validation and bounded page sizes.
- [ ] Implement structured typed response schemas and versioned API behavior.
- [ ] Integrate async PostgreSQL connection pooling and lifecycle cleanup.
- [ ] Add `GET /suggest` only after basic search works. (LATER)
- [ ] Add source/type/date filtering parameters.
- [ ] Return title, snippet, source, URL, type, published/updated date, and score where appropriate.
- [ ] Handle empty queries, strange Unicode, injection attempts, timeouts, and zero results.
- [ ] Restrict CORS to configured frontend origins.
- [ ] Add API request rate limiting and safe error messages before public exposure.
- [ ] Add structured logs, trace/request IDs, and latency metrics.
- [ ] Avoid running crawler loops inside FastAPI startup or request handlers.
- [ ] Add OpenAPI docs and representative response examples.
- [ ] Decide whether `frontend/app/api/search/route.ts` is a proxy or whether the frontend calls FastAPI directly; avoid two competing search implementations.

**Exit gate:** Public search API remains responsive while independent crawler workers are running.

## 10. Next.js frontend — MVP → HARDEN
- [x] Create initial Next.js app, homepage, search page, and search UI components.
- [ ] Replace demo/mock search results with the real FastAPI endpoint.
- [ ] Build a single prominent query box with submit/Enter and clear actions.
- [ ] Build accessible result cards with title, source, URL, snippet, and freshness.
- [ ] Add loading skeleton, no-result guidance, and retryable error state.
- [ ] Keep query and filters synchronized with the URL for shareable searches.
- [ ] Add source filters (docs/issues) and document-type chips.
- [ ] Add time filters when date metadata is reliable.
- [ ] Support keyboard navigation, visible focus, and responsive layouts.
- [ ] Check contrast, aria labels, semantic headings, and screen-reader announcements.
- [ ] Add safe outbound links, appropriate external-link behavior, and original-source attribution.
- [ ] Configure page metadata, favicon, canonical tags, robots and sitemap for the product website.
- [ ] Create an informative `/about` or `/how-it-works` page.
- [ ] Add analytics for searches and zero-result queries with privacy controls. (HARDEN)
- [ ] Add autocomplete/history/bookmarks only when usage justifies them. (LATER)
- [ ] Add nearby developer-event UI only when event ingestion and geo-filtering are available. (LATER)

**Exit gate:** A new user can search, inspect results, filter them, and open the original page on mobile or desktop.

## 11. Testing, evaluation, and security — MVP → HARDEN
- [ ] Add unit tests for URL parsing, normalization, deduplication, and scope rules.
- [ ] Add fixture-based tests for robots directives and status handling.
- [ ] Add parser fixtures for documentation pages, code blocks, malformed HTML, and encoding issues.
- [ ] Add tests for redirect loops, timeouts, huge responses, and unexpected content types.
- [ ] Add SSRF tests covering localhost/private IP, redirects, DNS resolution, and rebinding scenarios.
- [ ] Add frontier concurrency, expired-lease, and worker-kill recovery tests.
- [ ] Add content hash, canonicalization, update, and deletion tests.
- [ ] Add API integration tests against a temporary test database.
- [ ] Add full end-to-end test: local fixture site → crawl → index → search API → rendered result.
- [ ] Add tests for XSS-safe snippets and parameterized DB queries.
- [ ] Build an evaluation set with queries, relevant docs, expected sources, and known difficult cases.
- [ ] Measure Recall@10, MRR@10 or NDCG@10 and manually inspect failure modes.
- [ ] Track p50/p95 search latency and crawl throughput before optimization.
- [ ] Test no-results, spelling variants, versioned docs, GitHub issue names, and stale content.
- [ ] Run a secret scanner, dependency audit, static analysis, and formatting/type checks in CI.
- [ ] Load-test search separately from ingestion using realistic workloads.

**Exit gate:** A passing automated suite and a documented relevance/latency baseline exist.

## 12. Deployment, operations, and launch — HARDEN
- [ ] Containerize FastAPI, crawler worker, and Next.js separately.
- [ ] Run local services with Docker Compose and persistent PostgreSQL storage.
- [ ] Keep development, staging, and production configuration separate.
- [ ] Choose production hosting appropriate to a continuously running worker, not only serverless request handlers.
- [ ] Provision managed PostgreSQL or a properly backed-up PostgreSQL host.
- [ ] Run schema migrations as a controlled deployment step.
- [ ] Store secrets in environment/secret manager; rotate and revoke as needed.
- [ ] Configure HTTPS, DNS, CORS, security headers, and public rate limiting.
- [ ] Establish crawler CPU, memory, outbound bandwidth, and storage budgets.
- [ ] Add worker readiness/health information, structured logs, and error alerting.
- [ ] Monitor documents indexed, frontier backlog, crawl failure rate, host 429s, index lag, and search p95.
- [ ] Add database backups and actually test a restore procedure.
- [ ] Implement retention and cleanup for old fetch logs and failed jobs.
- [ ] Add CI for tests/lint and CD for deploying frontend, API, and worker.
- [ ] Provide a crawler stop/disable switch if sources misbehave.
- [ ] Publish README architecture, local setup, screenshots, design tradeoffs, and observed system metrics.
- [ ] Release a small public beta and review actual query logs/feedback without collecting unnecessary personal data.
- [ ] Create bug-report, feature-request, and attribution/takedown channels.

**Exit gate:** A deployed user can search reliably; crawler and API can restart independently; failures are visible and recoverable.

## 13. Later-scale engineering (do not block MVP) — LATER
- [ ] Separate indexer into its own service and scale independently.
- [ ] Add a distributed event broker only when PostgreSQL frontier/outbox becomes a bottleneck.
- [ ] Coordinate per-host politeness across distributed workers.
- [ ] Add priority aging/fairness across many sources.
- [ ] Add adaptive recrawl scheduling based on content change rates.
- [ ] Add selective Playwright rendering for specifically approved JS-heavy sources.
- [ ] Add document version history/change detection.
- [ ] Add a source health/relevance dashboard and manual source curation workflow.
- [ ] Improve technical entity extraction (libraries, languages, versions, error codes).
- [ ] Add specialized result tabs: documentation, issues, discussions, events, and articles.
- [ ] Add hybrid semantic + lexical retrieval, reranking, and offline relevance experiments.
- [ ] Add multilingual content only with adequate quality evaluation.
- [ ] Add separate regional/event indexing where justified.
- [ ] Explore link-based authority signals only after validating quality and anti-spam behavior.
- [ ] Benchmark cost per 1,000 useful indexed documents and per 1,000 searches.
- [ ] Publish technical writeups explaining actual system measurements and tradeoffs.

## Success gates (in recommended order)

1. **M0 — Repository ready:** independently executable Next.js, FastAPI, and crawler packages.
2. **M1 — Vertical slice:** 50 allowed pages crawled and genuinely searchable from the UI.
3. **M2 — Durable crawler:** frontier leases, retries, robots, rate limits, recrawls, and restart recovery.
4. **M3 — Developer corpus:** documentation plus GitHub issues indexed through appropriate source adapters.
5. **M4 — Search quality:** relevance evaluation, filters, snippets, stable pagination, and measured latency.
6. **M5 — Public beta:** secure hosting, CI, monitoring, backups, source policies, feedback loop.
7. **M6 — Expansion:** more connectors and advanced ranking based on actual user demand.

## Critical decisions

- `backend/` is FastAPI. `crawler/` is plain async Python, **not** another FastAPI app.
- Both are independent Poetry projects; frontend uses Node/Next.js.
- Share PostgreSQL initially. Keep table ownership and schema/migrations explicit.
- A crawler is not automatically a search engine: indexing, retrieval, and relevance evaluation are separate deliverables.
- Crawl only approved sources, with source-specific rules. Do not assume public accessibility implies blanket reuse rights.
- Start with PostgreSQL full-text search. Do not require Redis, Kafka, Kubernetes, vector databases, or AI agents for the initial release.
- Keep API ingestors (e.g., GitHub) separate from general HTML crawling, but normalize both into one document schema.

### Reference specifications
- [RFC 9309: Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309.html)
- [PostgreSQL full-text search](https://www.postgresql.org/docs/current/textsearch.html)
- [GitHub REST API best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
