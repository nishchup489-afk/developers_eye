<div align="center">

![Developer's Eye — search beyond the surface](assets/developers-eye-banner.png)

# Developer's Eye

**A search engine for developers, built from the crawl up.**

Discover documentation, code, and developer discussions through a search pipeline you can run, inspect, and improve yourself.

![Status: prototype](https://img.shields.io/badge/status-prototype-a855f7?style=flat-square)
![Python 3.14+](https://img.shields.io/badge/Python-3.14%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)

[Try locally](#try-the-interface) · [Run the engine](#run-the-full-system) · [Architecture](#how-it-works) · [Documentation](#documentation) · [Contribute](#contributing)

</div>

## Why build another search engine?

A developer's answer rarely lives in one place. The reference is in the docs, the implementation is on GitHub, and the explanation is buried in a discussion. Developer's Eye brings those kinds of resources into a searchable local corpus and makes the machinery behind the results visible.

It is also an exercise in building the whole system: deciding what to crawl, fetching it politely, extracting useful content, keeping indexes fresh, ranking results, and finding out where the pipeline went wrong. The repository records the decisions, incidents, and experiments along the way.

**This is a prototype you can run locally.** The interface has an explicit fixture-based demo mode; live search uses documents acquired by your own crawler and processed by your own indexer. Available source categories describe the product's organization; actual coverage depends on the sources you enable and successfully ingest.

## What makes it interesting

| Layer | What is here |
| --- | --- |
| **Search experience** | An animated eye, dedicated results pages, shareable queries, source filters, browser-local bookmarks, keyboard shortcuts, and reduced-motion support. |
| **Acquisition** | A configurable source registry, URL frontier, leases, retry/recovery, scoped discovery, HTML parsing, sitemaps, RSS/Atom, and mapped JSON API ingestion. |
| **Crawler policy** | Host allowlists, DNS/IP checks, pinned transport, robots handling, bounded redirects, and shared per-host pacing in PostgreSQL. |
| **Indexing** | Separate weighted text and code vectors, freshness-based selection, versioned index hashes, transactional writes, and vocabulary maintenance. |
| **Retrieval and ranking** | PostgreSQL full-text candidates, explicit `all` / `text` / `code` modes, candidate-set BM25 ranking, query-aware snippets, pagination, and explicit spelling suggestions. |
| **Optional AI overview** | Backend-owned Groq summaries grounded in signed search results, with PostgreSQL-backed quotas and caching. Configure a provider key to enable generation. |
| **Operations** | A read-only admin workspace for crawler activity, index coverage, corpus health, availability, host traffic, system capacity, and AI usage. |
| **Engineering evidence** | Unit and integration suites, ranking goldens, a relevance evaluation lab, architecture decisions, incident reports, and experiment records. |

The ranking lab includes deterministic checks and tools for judged evaluation. Real-corpus judged results are pending; see the [evaluation guide](backend/evaluation/README.md) for what the metrics establish.

## How it works

```mermaid
flowchart LR
    Sources["Enabled source registry"] --> Crawler["Crawler<br/>discover · fetch · parse"]
    Web["Approved websites<br/>feeds · APIs"] --> Crawler
    Crawler --> Documents[("PostgreSQL<br/>documents + frontier")]
    Documents --> Indexer["Indexer<br/>text + code vectors"]
    Indexer --> Index[("PostgreSQL<br/>search index + vocabulary")]
    Browser["Browser"] --> Next["Next.js<br/>same-origin server routes"]
    Next --> API["FastAPI<br/>retrieve · rank · snippet"]
    API --> Index
    API --> Documents
    API -. "optional signed-result summary" .-> Groq["Groq"]
```

**Four application processes, one shared database:** frontend, API, crawler, and indexer. Crawling and indexing happen outside search requests. The crawler stores documents; the indexer finds missing or stale rows; the API searches the prepared index.

PostgreSQL holds the frontier, extracted content, search vectors, vocabulary, and operational state. The local setup needs no separate search service or Redis server. The crawler distribution contains both `crawler` and `indexer` and depends on the backend package; the backend runs independently of the workers.

The frontend uses **Next.js 16, React 19, TypeScript, Tailwind CSS 4, and GSAP**. The Python services use **FastAPI, SQLAlchemy, asyncpg, Alembic, HTTPX, Beautiful Soup, and lxml**. PostgreSQL provides full-text search and `pg_trgm` vocabulary matching.

## Try the interface

Explore the search UI without PostgreSQL, Python, or provider keys. Use **Node.js 24** and npm, matching the repository's CI configuration.

```powershell
git clone https://github.com/nishchup489-afk/developers_eye.git
cd developers_eye/frontend
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000). Leave `BACKEND_URL` unset for the labeled demo, which searches curated fixtures. If you already have `frontend/.env.local`, remove or comment out `BACKEND_URL` and restart Next.js to return to demo mode.

For a production build, stop the development server, run `npm run build`, then `npm run start` from `frontend/`.

## Run the full system

The commands below use **PowerShell**, starting from the repository root unless a step says otherwise. On macOS/Linux, use `cp` in place of `Copy-Item`; the Poetry and npm commands are the same. If you followed the demo above, return to the repository root first.

### 1. Prepare the tools and database

Install **Python 3.14+**, **Poetry 2.x**, **Node.js 24**, and **PostgreSQL 16**. Have PostgreSQL running and its command-line tools available. CI and the deployment stack use PostgreSQL 16.

Create an application database and a separate, disposable test database:

```powershell
createdb -h 127.0.0.1 -U postgres developers_eye
createdb -h 127.0.0.1 -U postgres developers_eye_test
```

These commands use your existing `postgres` role and password. Substitute your own role if needed. The migration role must be able to install `pg_trgm`, or your database administrator must install it first.

### 2. Create the environment files

Copy each example only if its destination does not already exist, then edit the copies:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
Copy-Item .env.local.example .env.local
```

| File | Set this | Purpose |
| --- | --- | --- |
| `backend/.env` | `DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@127.0.0.1:5432/developers_eye` | Shared application database for the API, crawler, and indexer. |
| `backend/.env` | `CRAWLER_REPORT_API_KEY` | A random secret of at least 32 characters for backend admin reports. |
| `frontend/.env.local` | `BACKEND_URL=http://127.0.0.1:8000` | Switches public search from demo fixtures to the live API. |
| `frontend/.env.local` | `CRAWLER_REPORT_API_URL=http://127.0.0.1:8000/admin/crawler/report` | Backend reporting endpoint for the admin proxy. |
| `frontend/.env.local` | `CRAWLER_REPORT_API_KEY` | The **same** reporting key as `backend/.env`. |
| Repository-root `.env.local` | `TEST_DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@127.0.0.1:5432/developers_eye_test` | Test database, separate from application data. |

Generate each secret separately:

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Use your actual password in the URLs and percent-encode reserved characters in credentials. Keep the `postgresql+asyncpg://` driver prefix.

The backend's settings load `backend/.env` by its file path, including when used by crawler/indexer processes. The root `.env.local` is for tests: only test-related keys are loaded, and existing shell variables take precedence. `frontend/.env.local` belongs to Next.js. The crawler's current `.env.example` is empty; a separate crawler environment file is unnecessary.

<details>
<summary><strong>Optional environment settings</strong></summary>

| Setting | Where | When to use it |
| --- | --- | --- |
| `GROQ_API_KEY`, `GROQ_MODEL`, `AI_OVERVIEW` | `backend/.env` | Enable/configure AI summaries. Public lexical search works without a provider key. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | `frontend/.env.local` | GitHub OAuth for the admin workspace. |
| `ADMIN_APP_URL`, `ADMIN_GITHUB_IDS`, `ADMIN_SESSION_SECRET` | `frontend/.env.local` | Admin origin, numeric account allowlist, and a separate random signing secret. |
| `ADMIN_VIEWER_ACCESS`, `ADMIN_VIEWER_GITHUB_IDS` | `frontend/.env.local` | Optional read-only viewer access; default access mode is `off`. |
| `ADMIN_DB_BUDGET_GB`, `ADMIN_TARGET_DOCUMENTS`, `ADMIN_HOST_MIN_INTERVAL_SECONDS`, `ADMIN_EVENT_RETENTION_DAYS` | `backend/.env` | Capacity planning and operational checks. |
| `INDEXER_*` | Indexer process environment | Batch size, concurrency, polling, sharding, and index version; see [indexer configuration](crawler/src/indexer/docs/config.md). |
| `SEARCH_*` | API process environment | Search limits, deadlines, and ranking configuration; see [search configuration](backend/src/backend/search/config.py) and [request limits](backend/src/backend/api/search.py). |

`INDEXER_*` and `SEARCH_*` configuration readers use the process environment directly. In PowerShell, export values with `$env:NAME = "value"` before launching that process. The API command below also uses Uvicorn's `--env-file .env` to load values from `backend/.env` into its environment.

Keep provider keys, OAuth secrets, session secrets, and the reporting key server-side. Use the example files as the configuration reference and leave secret-bearing copies out of commits.

</details>

### 3. Install the Python packages and apply migrations

```powershell
cd backend
poetry install
poetry run alembic upgrade head
cd ../crawler
poetry install
cd ..
```

The crawler's Poetry configuration installs `../backend` as a local dependency and includes the indexer package. No custom `PYTHONPATH` is required.

### 4. Enable a source and seed the frontier

**All bundled source definitions currently start with `is_enabled: false`.** Bootstrap alone will register them but will not produce crawl work until you enable a source.

Before the first bootstrap, edit a definition in [`crawler/src/crawler/seed/sources/`](crawler/src/crawler/seed/sources). Choose a source you intend to crawl, set `is_enabled` to `true`, and set a small `config.max_pages` and `config.max_depth` for your first run. Review its `allowed_hosts` and `allowed_path_prefixes` to keep the scope clear. The crawler still applies its fetch policy and robots checks.

```powershell
cd crawler
poetry run python -m crawler.main bootstrap
cd ..
```

`bootstrap` registers sources and discovers initial targets. Source seeding inserts new slugs and leaves existing database rows unchanged. If you already bootstrapped with disabled definitions, update those rows through the [source registry helpers](crawler/src/crawler/seed/registry.py), including `set_source_enabled` / `update_source`, then run `poetry run python -m crawler.main discover` from `crawler/`. Editing JSON and rerunning seed will not update an existing source.

See the [seed guide](crawler/src/crawler/seed/guide.md) and [sitemap discovery guide](crawler/src/crawler/seed/docs/sitemap_discovery.md) for the source/discovery model.

### 5. Start the four processes

Open four terminals at the repository root and keep each process running:

| Terminal | Working directory | Command |
| --- | --- | --- |
| **API** | `cd backend` | `poetry run uvicorn backend.main:app --reload --env-file .env --host 127.0.0.1 --port 8000` |
| **Crawler** | `cd crawler` | `poetry run python -m crawler.worker.runner --forever --batch-size 5 --concurrency 2` |
| **Indexer** | `cd crawler` | `poetry run python -m indexer.worker.runner --forever --batch-size 100 --concurrency 2` |
| **Frontend** | `cd frontend` | Run `npm ci` once, then `npm run dev`. |

Use `Ctrl+C` to stop a process. Apply new migrations before restarting workers after schema changes.

For a bounded first run, replace `--forever` with `--once` on each worker. A one-shot invocation processes one batch, so repeat it or switch to continuous mode to drain a larger backlog.

### 6. Follow the first document into search

1. Open [API health](http://127.0.0.1:8000/health) and [database health](http://127.0.0.1:8000/health/db).
2. Let the crawler fetch an enabled source and persist an available document.
3. Let the indexer build its text/code vectors.
4. Search for a term from that document at [localhost:3000](http://localhost:3000).
5. Inspect requests through [FastAPI Swagger UI](http://127.0.0.1:8000/docs) or [ReDoc](http://127.0.0.1:8000/redoc).

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/search?q=python&mode=all&limit=10'
```

From `crawler/`, these read-only commands show crawl activity and index coverage:

```powershell
poetry run python -m crawler.worker.reporting --days 7
poetry run python -m indexer.reporting
```

An empty result set is normal until matching documents have been crawled and indexed. Once `BACKEND_URL` is set, upstream failures are surfaced as errors; live requests do not fall back to fixtures.

## Inside the admin workspace

Open [localhost:3000/admin](http://localhost:3000/admin) to inspect the pipeline. The workspace is currently read-only; worker execution stays in the terminal.

| Page | What you can inspect |
| --- | --- |
| `/admin/crawler` | Stored documents, extracted content and metadata, crawl attempts, redirects, failures, frontier state, stage events, and worker heartbeats. |
| `/admin/indexer` | Index coverage, missing/stale documents, worker activity, and vocabulary reporting. |
| `/admin/corpus` | Corpus composition and search-related statistics. |
| `/admin/availability` | Search availability and recorded outcomes. |
| `/admin/hosts` | Per-host traffic, errors, throttling, and pacing signals. |
| `/admin/system` | Database size, capacity projections, table sizes, connections, and problem checks. |
| `/admin/ai-usage` | AI overview token usage and related reporting. |

### Configure GitHub sign-in

1. Register a GitHub OAuth App with homepage `http://localhost:3000` and callback **`http://localhost:3000/api/auth/github/callback`**.
2. In `frontend/.env.local`, set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `ADMIN_APP_URL=http://localhost:3000`.
3. Set `ADMIN_GITHUB_IDS` to your **numeric GitHub user ID**, not your username. Separate multiple IDs with commas. An empty administrator allowlist grants no administrator access.
4. Generate a separate random `ADMIN_SESSION_SECRET` of at least 32 characters. Check that the reporting key matches `backend/.env`.
5. Restart Next.js and sign in through `/admin`.

Use `localhost` consistently so the browser host matches your OAuth callback. Optional viewer modes and the full session/authentication contract are documented in the [frontend guide](frontend/README.md#github-setup).

## Vocabulary and index maintenance

The continuous indexer maintains vocabulary incrementally, including draining vocabulary changes. There is no additional vocabulary worker to start for a normal local run.

For a deliberate backfill or vocabulary repair, stop crawler/indexer writers first. From `crawler/`:

```powershell
poetry run python -m indexer.vocabulary_rebuild --once
```

For an explicit reindex request, preview the affected rows, then mark them for the normal worker to rebuild:

```powershell
poetry run python -m indexer.reindex --document-id 42 --dry-run
poetry run python -m indexer.reindex --document-id 42
```

Replace `42` with a document ID from your database. Reindexing marks metadata and leaves existing searchable vectors in place until rebuilt. Read the [operations guide](crawler/src/indexer/operations.md) before a full rebuild or index-version change.

## Tests you can actually run

The repository has one orchestrator over the native Python and frontend test runners. Configure `TEST_DATABASE_URL` in the **root** `.env.local` first. Its database name must contain `test`; database-backed tests can create/drop tables, so use only the disposable database.

Apply migrations to that database in a separate terminal. From the repository root:

```powershell
cd backend
$env:DATABASE_URL = "postgresql+asyncpg://postgres:YOUR_PASSWORD@127.0.0.1:5432/developers_eye_test"
poetry run alembic upgrade head
Remove-Item Env:DATABASE_URL
cd ..
```

Removing this override returns later application commands to the URL in `backend/.env`. Then run:

```powershell
python scripts/run_all_tests.py --list
python scripts/run_all_tests.py --with-build --save
```

For a quicker run, use `python scripts/run_all_tests.py` without flags: it includes the Python suites plus frontend lint, type checking, and unit checks. `--with-build` adds the production frontend build and suites that depend on it. `--save` writes HTML, text, and JSON reports under `tests/reports/`. The runner can reuse the Poetry environments; if your shell has no `python` command, run it from `crawler/` as `poetry run python ../scripts/run_all_tests.py` with the same flags.

<details>
<summary><strong>Run individual suites</strong></summary>

From `backend/`:

```powershell
poetry run pytest -v
```

From `crawler/`:

```powershell
poetry run pytest tests/crawler -v
poetry run pytest tests/indexer -v
```

From `frontend/`:

```powershell
npm run lint
npm run test:search:unit
npm run test:admin:unit
npm run build
npm run test:integration
npm run test:admin
npm run test:admin:routes
npm run test:overview:routes
```

The HTTP/frontend integration tests use local fixtures and mocked upstreams. Live-network tests have their own setup requirements. Run database suites sequentially when sharing a test database. Missing-database skips do not establish that persistence works.

</details>

For suite coverage and prerequisites, use the [test index](tests/test-index-of-whole-app.md), [crawler tests guide](crawler/tests/README.md), [frontend tests guide](frontend/tests/README.md), and [relevance lab](backend/evaluation/README.md).

## Documentation

| If you want to… | Start here |
| --- | --- |
| Understand the repository and handoff | [Technical handoff](technical_handoff.md) |
| Run or modify the API | [Backend guide](backend/README.md) |
| Work on the interface and admin auth | [Frontend guide](frontend/README.md) |
| Understand crawling and discovery | [Source guide](crawler/src/crawler/seed/guide.md) · [Policy guide](crawler/src/crawler/policy_and_politeness/README.md) |
| Work on indexing and freshness | [Indexer guide](crawler/src/indexer/README.md) · [Operations](crawler/src/indexer/operations.md) |
| Configure AI summaries | [AI overview setup and API contract](backend/docs/ai_overview.md) |
| Inspect API routes and boundaries | [API map](0_tech_docs/infra/system-architecture/api-map.md) · [Frontend API reference](frontend/public/api-reference.md) |
| Learn why a design exists | [Technical docs](0_tech_docs/README.md) · [Decisions, incidents, and experiments](0_tech_docs/record-index.md) |
| Read the project's development history | [Engineering journal](0_tech_docs/journal/README.md) |
| Find tests and what they prove | [Test index](tests/test-index-of-whole-app.md) · [Test-case catalog](tests/all-test-cases-that-were-tested/index.md) |
| Deploy the stack | [Deployment guide](deploy/README.md) |

Package guides describe how components work. `0_tech_docs/` records why they work that way. ADRs capture decisions; incident reports capture failures and fixes; experiments record a question, method, and evidence. Several architecture documents are explicitly dated snapshots: use their reviewed commit and the current implementation when assessing status.

The frontend also serves a documentation page at [localhost:3000/docs](http://localhost:3000/docs). For the running backend's implemented HTTP contract, use its Swagger UI at port `8000`; reference documents can include proposed routes.

<details>
<summary><strong>Repository map and documentation utilities</strong></summary>

```text
developers_eye/
├── frontend/              Next.js search experience and admin workspace
├── backend/               FastAPI, models, migrations, retrieval, and ranking
├── crawler/
│   ├── src/crawler/       Source registry, frontier, fetch/parse/write pipeline
│   ├── src/indexer/       Analysis, vectors, vocabulary, and index workers
│   └── tests/             Crawler and indexer suites
├── 0_tech_docs/            Architecture, decisions, incidents, and experiments
├── deploy/                Docker Compose, Caddy, PostgreSQL, and backup scripts
├── scripts/               Test orchestration and documentation generators
├── tests/                 Cross-project indexes and generated test reports
└── assets/                Project artwork
```

Run the relevant generator from the repository root after changing routes, records, or test inventory:

```powershell
python scripts/update_api_map.py
python scripts/update_record_index.py
python scripts/update_test_index.py
python scripts/update_docs_nav.py
```

These commands rewrite generated documentation. Each supports `--check` to check for stale output without writing it. The navigation generator adds or refreshes documentation maps across README files. Review the generated diff before committing.

</details>

## Deployment

[`deploy/docker-compose.yml`](deploy/docker-compose.yml) provides a single-server stack: PostgreSQL, a migration job, FastAPI, crawler and indexer workers, maintenance, Next.js, and Caddy for HTTPS.

Copy `deploy/.env.example` to `deploy/.env`, configure the domain, database password, and application secrets, then follow the [deployment guide](deploy/README.md). The Compose configuration is sized for a server; use the manual instructions above for a smaller local development run. The deployment guide covers upgrades, scaling, backups, and restore checks.

## When something goes sideways

| Symptom | Check |
| --- | --- |
| The UI still says demo | Set `BACKEND_URL` in `frontend/.env.local` and restart Next.js. |
| The crawler is idle | Enable a source **before first seed**, or update its existing database row, then run discovery. Check source scope, due times, and policy decisions. |
| Documents exist but searches are empty | Check that the indexer is running, migrations are current, and your query matches available indexed content. Use `indexer.reporting`. |
| The API fails during startup | Verify `DATABASE_URL`, PostgreSQL connectivity, and `alembic upgrade head`. Startup loads corpus statistics from the database. |
| Admin login is denied | Check numeric GitHub IDs, OAuth credentials, the callback host, and `ADMIN_SESSION_SECRET`. |
| Admin reports fail | Check `CRAWLER_REPORT_API_URL` and matching report keys in frontend/backend configuration. |
| Database tests skip | Set root `.env.local` → `TEST_DATABASE_URL`; create/migrate the test database and inspect the runner's diagnostics. |
| An `INDEXER_*` or `SEARCH_*` setting has no effect | Export it into that process's environment and restart the process. |
| AI overview is unavailable | Check the backend's Groq configuration, migrations, provider response, and quota state. See the [AI guide](backend/docs/ai_overview.md). |

## Contributing

Start with an [existing issue](https://github.com/nishchup489-afk/developers_eye/issues), or open one with a concrete problem, a reproducible example, and the behavior you expected.

1. Create a focused branch and read the package guide plus relevant technical records. Follow any `AGENTS.md` instructions in the area you change.
2. Keep acquisition, indexing, and query serving within their existing process boundaries.
3. Add or update tests when behavior changes, run the relevant suites, and report skipped or unrun checks explicitly.
4. Update the affected docs and regenerate indexes when their inputs change. Keep secrets and generated runtime artifacts out of the diff.
5. Open a pull request explaining the problem, the resulting behavior, and how you validated it.

The repository does not currently include a `CONTRIBUTING.md`; this section is the contribution guide until a dedicated one is added.

## Built by

Created by [Nish](https://github.com/nishchup489-afk), with the engineering process documented alongside the code.

| Find me / the project | Link |
| --- | --- |
| GitHub | [nishchup489-afk](https://github.com/nishchup489-afk) |
| Portfolio | |
| Blog | |
| X | |
| LinkedIn | |
| Live site | |

<!-- Personal and live-site URLs intentionally left blank for the maintainer. -->
