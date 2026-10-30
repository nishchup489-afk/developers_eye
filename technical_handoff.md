# Developer's Eye technical handoff

Status as of 2026-10-27 (commit `d3d74bb` on `main`, one commit ahead of `origin/main`).

Developer's Eye is a developer-focused search engine built from the crawler up. Today the crawler, the document store, the indexer and the admin monitoring console work end to end. Public search does not yet query the index: the web search page runs on a labeled demo collection until a backend `GET /search` endpoint exists.

```
Discover → Crawl → Parse → Process → Persist → Index → (Rank → Search: not built yet)
```

## 1. Architecture

Four processes share one PostgreSQL database. They never call each other directly except the frontend, which proxies admin requests to the backend.

```
 seed registry (JSON/CSV)
        │  crawler.main bootstrap
        ▼
 ┌──────────────┐   claims leased rows    ┌───────────────┐
 │ crawl_target │◀───────────────────────▶│ crawler worker│  fetch → policy → parse → process → write
 └──────────────┘   enqueues child links  └──────┬────────┘
                                                 │ document, crawl_attempt, crawl_event, crawl_worker
                                                 ▼
                                          ┌──────────────┐  selects missing/stale  ┌────────────────┐
                                          │  PostgreSQL  │◀───────────────────────▶│ indexer worker │
                                          └──────┬───────┘   writes search_index   └────────────────┘
                                                 │ read-only reports
                                                 ▼
                                          ┌──────────────┐  Bearer CRAWLER_REPORT_API_KEY  ┌──────────────────────┐
                                          │ FastAPI      │◀────────────────────────────────│ Next.js server routes │
                                          │ backend      │                                 │ (GitHub OAuth admin)  │
                                          └──────────────┘                                 └──────────────────────┘
```

Design images in the repo root: `Developer’s Eye System Architecture Diagram-2.png` and `Developer’s Eye Complete System Design-1.png`.

### Repository layout

| Path | What lives there |
| --- | --- |
| `backend/` | Poetry package `backend`: FastAPI app, SQLAlchemy models, Pydantic schemas, Alembic migrations, read-only reporting services. Owns the database schema. |
| `crawler/` | Poetry package with two importable packages, `crawler` and `indexer`, both under `crawler/src/`. Depends on `../backend` (path dependency) for models and the session factory. |
| `frontend/` | Next.js 16 / React 19 app: public search UI, `/docs` page, and the GitHub-authenticated `/admin` console. |
| `crawler/logs/` | Rotating crawler worker logs (see known gaps: these are tracked in git). |
| `bs.py` | Scratch file of commented-out experiments. Not used by anything. |

### Stack

Python 3.14, asyncio, HTTPX, Beautiful Soup + lxml, defusedxml, SQLAlchemy 2 (async, asyncpg), Alembic, FastAPI, pydantic-settings, Rich (logging). Frontend: Next.js 16.3, React 19.2, TypeScript, Tailwind 4, GSAP and three.js for the animated eye. Node 22.18+ is needed for the TypeScript-stripping unit tests.

## 2. Components

### 2.1 Database (`backend/src/backend/models`, `backend/alembic`)

| Table | Model file | Purpose |
| --- | --- | --- |
| `source` | `source.py` | Registered sites/feeds/APIs: `slug`, `kind` (`website`, `rss`, `api` only), `base_url`, `allowed_hosts`, `crawl_interval_seconds`, `is_enabled`, and a JSON `config` (`max_depth` default 3, `max_pages` default 10000, optional `allowed_path_prefixes`). |
| `crawl_target` | `crawler_frontier.py` | The URL frontier: `fetch_url`, `normalized_url`, `depth`, `kind`, `state`, `priority`, `next_fetch_at`, `lease_until`, `failure_count`, `discovered_from_id`. |
| `crawl_attempt` | `crawl_attempt.py` | One row per fetch attempt: status, outcome, error, bytes, timing `telemetry`, own `lease_until`. |
| `crawl_event` / `crawl_worker` | `crawl_monitor.py` | Pipeline stage events and worker heartbeats used by the admin monitor. |
| `document` | `documents.py` | Extracted content (title, description, body, metadata, `content_hash`), soft availability (`is_available`, `unavailable_at`, `unavailable_http_status`), `updated_at` freshness clock. Raw HTML is not stored. |
| `robots_cache` | `robot_cache.py` | Cached robots.txt per origin with expiry. |
| `search_index` | `search_index.py` | One row per document: `search_vector` and `code_vector` (`TSVECTOR`, GIN indexed), `indexed_hash` (`v<version>:<sha256>`), `indexed_at`. |

Migration chain (oldest first): `715c87a9c745` initial schema → `b61e204ac812` crawler observability → `c72f318bd923` crawl depth → `d83a429ce034` attempt leases → `e94b530df145` document availability → `28efc23fadfc` search index `code_vector` (current head). `backend/schema.sql` is a hand-kept snapshot; Alembic is the source of truth. Per-table notes are in `backend/docs/db/`.

### 2.2 Backend API (`backend/src/backend`)

`main.py` builds the FastAPI app, includes two routers and allows CORS from `localhost`/`127.0.0.1` on ports 3000 and 4173.

| Route | Auth | Notes |
| --- | --- | --- |
| `GET /`, `GET /health` | none | Liveness. |
| `GET /health/db` | none | Runs a query and returns database name and user. |
| `GET /admin/crawler/report` | Bearer key | `days` 1–365, `top_sources` 1–100, `recent_errors` 0–100. |
| `GET /admin/crawler/monitor` | Bearer key | Live events, frontier, documents, workers; paging and search params. |
| `GET /admin/crawler/documents/{id}` | Bearer key | Stored document detail. |
| `GET /admin/crawler/attempts/{id}` | Bearer key | Crawl attempt detail. |
| `GET /admin/indexer/report` | Bearer key | Index coverage, optional `source_id`. |

All admin routes are read-only and share `CRAWLER_REPORT_API_KEY`. Query logic lives in `services/crawler_reporting.py`, `services/crawler_monitoring.py` and `services/indexer_reporting.py`; the backend has no import dependency on the crawler (enforced by `backend/tests/test_package_boundary.py`).

There is **no `GET /search` endpoint yet**.

### 2.3 Crawler (`crawler/src/crawler`)

| Package | Responsibility |
| --- | --- |
| `seed/` | Source registry (`sources/*.json`, `developers_eye_source_registry.csv/.xlsx`), `seed.py` upserts sources, `discovery.py` / `sitemap.py` / `feeds.py` / `api_discovery.py` insert initial targets. Entry point `crawler.main {seed,discover,bootstrap}`. |
| `frontier/` | URL normalization (`urls.py`), crawl scope by depth/page budget/path prefix (`scope.py`), enqueueing (`repository.py`). |
| `schedular/` | Claiming due targets with leases, completing, failing with exponential backoff, recovering expired leases (`repository.py`). |
| `policy_and_politeness/` | Host allowlist, DNS/IP safety (blocks private ranges, pins resolved IPs), robots.txt fetch/cache/rules, per-host politeness delays and concurrency, redirect checks, and `policy_coordinator.py` that runs them in order. |
| `fetcher/` | HTTPX hop fetcher with size/media-type limits and typed errors. |
| `parser/` | HTML extraction (body, metadata, links, robots meta), sitemaps, RSS/Atom, configurable JSON API records. |
| `processing/` | Normalization, classification, fingerprinting (`content_hash`), keep/skip decisions. |
| `writer/` | Persists documents and attempts. |
| `worker/` | `runner.py` (claim → run jobs under a semaphore → lease recovery), `jobs/jobs.py` (one target through the whole pipeline in a lease-safe transaction, with deadlock retry), `recovery.py`, `telemetry.py` and `monitoring.py` (stage events, heartbeats), `reporting.py` (CLI wrapper over the backend report), `logging_config.py`. |

Runner flags: `--once` (default) or `--forever`, `--batch-size 5`, `--concurrency 2`, `--lease-seconds 300` (min 30), `--job-timeout-seconds 240` (must be at least 15 s under the lease), `--poll-seconds 10`, `--source-id`, `--log-level`. A worker never claims more than it can start immediately, so leases do not expire while queued.

### 2.4 Indexer (`crawler/src/indexer`)

Runs as its own process; it has no queue or lease table. It finds work by comparing `document.updated_at` and the active index version against `search_index`.

`selector.py` (missing/stale/old-version candidates, removal candidates) → `builder.py` (prepare snapshot, compute hash) → `analyzer.py` (weighted fields) → `vector.py` (`to_tsvector` expressions, `english` for prose and `simple` for code) → `service.py` → `writer.py` (locks the document `FOR UPDATE`, re-checks freshness, upserts or deletes in one transaction) → `repository.py` (SQL). Statuses: `INDEXED`, `UNCHANGED`, `STALE`, `REMOVED`, `SKIPPED`, `FAILED`.

Operator tools: `indexer.worker.runner`, `indexer.reporting` (read-only JSON coverage), `indexer.reindex` (`--document-id N` or `--all`, with `--dry-run`; marks `indexed_hash = 'reindex:pending'`). To rebuild everything after an analyzer change, bump `INDEXER_INDEX_VERSION` on the worker and the backend and restart both. Details: `crawler/src/indexer/operations.md`.

### 2.5 Frontend (`frontend/`)

- Public: `/` landing with the animated eye, `/search?q=&source=` results, `/docs` API overview. The browser calls same-origin `/api/search`, which forwards to `BACKEND_URL/search` when set, otherwise returns demo results from `lib/demo.ts` marked `mode: "demo"`. Saved results live in browser `localStorage`.
- Admin: `/admin/login` → GitHub OAuth (state + S256 PKCE) → signed HttpOnly session cookie (8 h), checked against the `ADMIN_GITHUB_IDS` allowlist on every request. Pages `/admin/crawler` (documents, attempts, live pipeline, frontier, sources, workers) and `/admin/indexer` (coverage).
- Server routes `/api/admin/crawler/{report,monitor,inspect}` and `/api/admin/indexer/report` verify the session and forward to the backend with the service key (`lib/crawler-proxy.ts`). The backend base is derived from `CRAWLER_REPORT_API_URL`, which must end in `/admin/crawler/report`.
- HTTP uses axios: all instances in `lib/axios.js`: `api` in the browser, `backend` for FastAPI and GitHub (fetch adapter, no-store, redirects refused, 15 s admin / 10 s search and OAuth timeouts).
- Next.js 16 has breaking changes from earlier versions; read `frontend/AGENTS.md` before editing.

## 3. Configuration

Never commit real values. Example files: `backend/.env.example`, `frontend/.env.example`.

| Variable | Read by | Required | Notes |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend, crawler, indexer (`backend/.env`) | yes | `postgresql+asyncpg://user:pass@host/developers_eye` |
| `CRAWLER_REPORT_API_KEY` | backend and frontend | for admin | Same random value (32+ chars) in both. |
| `INDEXER_INDEX_VERSION` | backend and indexer worker | no (1) | Must match between the two or the coverage report is wrong. |
| `APP_NAME`, `APP_ENV`, `DEBUG` | backend | no | pydantic-settings defaults. |
| `INDEXER_BATCH_SIZE`, `INDEXER_CONCURRENCY`, `INDEXER_POLL_SECONDS`, `INDEXER_MAX_DOCUMENT_CHARS`, `INDEXER_TEXT_SEARCH_CONFIG`, `INDEXER_CODE_SEARCH_CONFIG`, `INDEXER_LOG_LEVEL` | indexer | no | Defaults 100, 2, 10, 1000000, `english`, `simple`, `INFO`. Process environment only; the indexer does not read `.env` files. |
| `BACKEND_URL` | frontend | no | Unset = demo search. |
| `ADMIN_APP_URL`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `ADMIN_GITHUB_IDS`, `ADMIN_SESSION_SECRET` | frontend | for admin | Server-only; never prefix with `NEXT_PUBLIC_`. Production `ADMIN_APP_URL` must be HTTPS. |
| `CRAWLER_REPORT_API_URL` | frontend | for admin | e.g. `http://127.0.0.1:8000/admin/crawler/report` |
| `NEXT_BUILD_DIR` | frontend | no | Alternate build dir for isolated test builds. |
| `TEST_DATABASE_URL` | Python tests | no | Enables PostgreSQL-backed tests; they skip without it. Point it at a throwaway database. |

The crawler's user agent is `DevelopersEyeBot` (`crawler/src/crawler/config.py`).

## 4. Running locally (Windows, PowerShell)

Prerequisites: Python 3.14, Poetry, Node 22.18+ (or 24), PostgreSQL.

```powershell
# 1. Backend: install, migrate, serve on :8000
cd backend
poetry install
copy .env.example .env          # then set DATABASE_URL and CRAWLER_REPORT_API_KEY
poetry run alembic -c alembic.ini upgrade head
poetry run uvicorn backend.main:app --reload

# 2. Crawler: register sources and initial targets, then crawl
cd ..\crawler
poetry install
poetry run python -m crawler.main bootstrap
poetry run python -m crawler.worker.runner --forever --concurrency 2

# 3. Indexer (separate terminal, from crawler/)
poetry run python -m indexer.worker.runner --forever --batch-size 100 --concurrency 2

# 4. Frontend
cd ..\frontend
npm install
copy .env.example .env.local    # fill in admin variables if you need /admin
npm run dev
```

Web: http://localhost:3000 · API docs: http://127.0.0.1:8000/docs · Admin: http://localhost:3000/admin (use `localhost`, not `127.0.0.1`, to match the OAuth callback cookie).

Always apply migrations before restarting workers after a schema change. Useful read-only reports: `poetry run python -m crawler.worker.reporting --days 7` and `poetry run python -m indexer.reporting`.

## 5. Testing

| Suite | Command | Needs |
| --- | --- | --- |
| Crawler offline regression | `.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler backend/tests crawler/tests -q --ignore=crawler/src/crawler/worker/tests/test_live_pipeline.py --ignore=crawler/src/crawler/writer/tests/test_database_writer.py --ignore=crawler/src/crawler/policy_and_politeness/tests/test_dns_policy.py` (repo root) | nothing |
| DNS policy (own runner) | `.\crawler\.venv\Scripts\python.exe -m crawler.policy_and_politeness.tests.test_dns_policy` | network |
| Indexer | `poetry run pytest src/indexer/tests -v -rs` (from `crawler/`) | `TEST_DATABASE_URL` for the PostgreSQL lifecycle tests |
| PostgreSQL pipeline / writer | see `crawler/tests/README.md` and `crawler/src/crawler/worker/tests/README.md` | dedicated test database |
| Live crawl | `crawler/src/crawler/worker/tests/test_live_pipeline.py` | internet; run deliberately |
| Frontend | `npm run lint`, `npm run build`, `npm run test:integration` | production build for integration |
| Admin | `npm run test:admin:unit`, `npm run test:admin:routes`, `npm run test:admin` | Node 22.18+; build first for routes/integration |

Every tests folder has a `README.md` (how to run) and a `test_case.md` (what each test proves). A skipped PostgreSQL test is not a pass; set `TEST_DATABASE_URL` before claiming persistence works. Recent milestones from the commit log: 49 selector/analyzer/builder tests, 72 vector tests, 152 indexer tests passing.

## 6. Key technical decisions

- **PostgreSQL as the job queue.** Targets are claimed with leases (`lease_until`) in short transactions; crashed or timed-out work is recovered when the lease expires, so no external broker is needed. Each attempt records the lease it ran under, so recovery closes only the attempts that belong to an expired lease.
- **Two-stage URL validation.** Cheap syntax and allowlist checks first, then DNS resolution with private-network blocking and IP pinning before any request, to prevent SSRF through redirects or DNS rebinding.
- **Exponential backoff with failure counts** on `crawl_target`, plus per-host politeness delays and robots.txt caching.
- **Soft availability.** 404/410 marks a document unavailable instead of deleting it; the indexer then removes its index row.
- **Indexer has no queue.** Freshness is derived from `document.updated_at` and a versioned `indexed_hash`, so reindexing is "bump the version" or "mark pending", and the writer's `SELECT … FOR UPDATE` keeps a document and its index consistent.
- **Two tsvectors.** `english` stemming for prose, `simple` for identifiers and code tokens.
- **Read-only admin plane.** The console cannot start, stop or delete anything; it only reads reports through a server-held key behind GitHub OAuth.

## 7. Known gaps and risks

1. **A live reporting key is in git history.** `crawler/src/crawler/.env.local` is tracked (added in `5752803`, already on `origin/main`) and contains a `CRAWLER_REPORT_API_KEY` identical to the one in `backend/.env`. Rotate the key in `backend/.env` and `frontend/.env.local`, then `git rm --cached` the three tracked `crawler/src/crawler/.env*` files (keep `.env.example`). The local `.gitignore` there uses `*.env` patterns that do not match `.env.local`.
2. **No search endpoint or ranking.** `search_index` is populated, but there is no `GET /search`, no `ts_rank`/BM25-style scoring and no snippet generation. The frontend contract is in `frontend/public/api-reference.md`.
3. **`code_vector` migration on non-empty tables.** `28efc23fadfc` adds `code_vector` as `NOT NULL` with no default, so `alembic upgrade` fails if `search_index` already has rows. Truncate the table first (the indexer rebuilds it) or add a server default.
4. **Indexer concurrency is untested.** Concurrent writers and a source update while the writer waits on the row lock are not covered (see `crawler/src/indexer/README.md`). A document that always fails validation is reselected every poll because there is no failure backoff.
5. **Coverage report is not a single snapshot.** Two queries at READ COMMITTED; numbers can drift slightly under load. No throughput or failure history is persisted for the indexer.
6. **Tracked noise.** `crawler/logs/crawler.log.1`–`.5` (rotated names escape the `*.log` rule; about 110k lines were committed in `ebe964b`) and `frontend/.npm-cache/` are in git despite `.gitignore`. Consider `git rm --cached` and adding `*.log.*`.
7. **Inconsistent run instructions.** The root `README.md` seeds with `crawler.seed.seed` and mentions `cp .env.example .env`; `backend/README.md` uses `crawler.main bootstrap`. Prefer `bootstrap`. The frontend README still describes running the backend through the crawler venv with a manual `PYTHONPATH`, which is no longer needed now that the crawler depends on the backend package.
8. **Stale indexer README note.** `crawler/src/indexer/README.md` says `repository.py` is empty; it is implemented (185 lines).
9. **No container or CI setup.** There is no `compose.yaml`, Dockerfile or CI workflow; tests are run by hand. `crawler/DEVELOPERS_EYE_CHECKLIST.md` lists the original roadmap, and several of its early items are done but still unchecked.
10. **Scratch files.** `bs.py` at the root and `crawler/src/crawler/test/upadte_log/` (typo, a one-off duplicate of `update_log/`) can be removed or merged.
11. **Indexer reporting files.** `backend/src/backend/api/indexer_report.py` and `backend/src/backend/services/indexer_reporting.py`, missing from `0aedb4c`, were committed in `ebe964b`. Nothing is outstanding there.

## 8. Suggested next steps

1. Rotate the leaked key and untrack the `.env` files (gap 1).
2. Implement `GET /search` in the backend with `websearch_to_tsquery`, weighted `ts_rank_cd` over both vectors, source filters and `ts_headline` snippets, matching the contract the frontend already validates (`frontend/lib/search.ts`). Then set `BACKEND_URL` and drop demo mode.
3. Build the 30-query relevance evaluation set from the checklist before tuning ranking.
4. Add indexer failure backoff and the missing concurrency tests.
5. Add `compose.yaml` for PostgreSQL plus a CI workflow running the offline suites and `scripts/update_docs_nav.py --check`.

## 9. Keeping docs navigable

Every `README.md` ends with a generated **Documentation map** linking every tracked doc. After adding, moving or renaming a Markdown file, run from the repo root:

```powershell
python scripts/update_docs_nav.py
```

Use `--check` in CI to fail when a map is stale. Labels for files without a useful first heading are set in the script's `LABELS` table.
