<div align="center">

<img src="assets/homepage.png" alt="Developer's Eye home page" width="860">

# Developer's Eye

### Search built for developers, from the crawler up.

An open-source search engine for developer docs, built from scratch on PostgreSQL:<br>
crawler, indexer and BM25 ranking, with code-aware search.

[![CI](https://github.com/nishchup489-afk/developers_eye/actions/workflows/ci.yml/badge.svg)](https://github.com/nishchup489-afk/developers_eye/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/nishchup489-afk/developers_eye?style=flat&color=f5c542)](https://github.com/nishchup489-afk/developers_eye/stargazers)
[![Issues](https://img.shields.io/github/issues/nishchup489-afk/developers_eye?style=flat)](https://github.com/nishchup489-afk/developers_eye/issues)
[![Good first issues](https://img.shields.io/github/issues/nishchup489-afk/developers_eye/good%20first%20issue?style=flat&color=7057ff&label=good%20first%20issues)](https://github.com/nishchup489-afk/developers_eye/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-2ea44f?style=flat)](CONTRIBUTING.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-join%20the%20chat-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.gg/jxbRsFj3d)

**[Live demo](https://developers-eye.vercel.app)** ·
**[Discord](https://discord.gg/jxbRsFj3d)** ·
**[Quick start](#quick-start)** ·
**[Setup guide](setup-guide.md)** ·
**[Architecture](#architecture)** ·
**[Why it's built this way](0_tech_docs/README.md)** ·
**[Contribute](#contributing)**

Created by **Nish**

[![Portfolio](https://img.shields.io/badge/Portfolio-nish--chup-111111?style=for-the-badge&logo=vercel&logoColor=white)](https://nish-chup-one.vercel.app)
[![X](https://img.shields.io/badge/@Nishchup489-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/Nishchup489)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Sadnan%20Nishthup-0A66C2?style=for-the-badge)](https://www.linkedin.com/in/sadnan-nishthup-7405273a5/)

Docs site: *coming soon* · Blog: *coming soon*

</div>

---

## What is Developer's Eye?

**Developer's Eye** is a search engine for technical content. It crawls developer documentation, indexes it, and ranks results with its own BM25 implementation. There is no Elasticsearch, no vector database and no search library underneath: every stage, from the URL frontier to the snippet shown under a result, is code in this repository running on one PostgreSQL database.

It is also built to be read. Every major decision has a written record, every incident has a post-mortem, and every performance claim links to the experiment that produced it. An admin dashboard shows the crawler, indexer, database and search quality live.

Built in public, and designed to be understood, extended and improved by contributors.

> 💬 **Join the community on [Discord](https://discord.gg/jxbRsFj3d)** to ask questions, share what you are building, and follow development.

## Screenshots

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="assets/search-knowledge-panel.png" alt="Search results for python with the knowledge panel">
      <p align="center"><b>Results with a knowledge panel</b><br><sub>Ranked results, source filters and a Wikipedia summary beside them</sub></p>
    </td>
    <td width="50%" valign="top">
      <img src="assets/search-did-you-mean.png" alt="Did you mean suggestion for a misspelled query">
      <p align="center"><b>"Did you mean"</b><br><sub>Spelling correction from the index's own vocabulary</sub></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="assets/admin-hosts.png" alt="Admin dashboard hosts page">
      <p align="center"><b>Admin dashboard: hosts</b><br><sub>Request rate per host and the throttling signals that come before a ban</sub></p>
    </td>
    <td width="50%" valign="top" align="center">
      <img src="assets/mobile-knowledge-panel.png" alt="Knowledge panel on a phone" width="240">
      <p align="center"><b>Works on a phone</b><br><sub>The same search and knowledge panel at mobile width</sub></p>
    </td>
  </tr>
</table>

## Features at a glance

| | |
|---|---|
| **Search** | Three retrieval channels (text, code and title) merged per document, then ranked with BM25 · `All` / `Text` / `Code` modes · source filters · "did you mean" correction from a trigram vocabulary · query-aware snippets · optional AI overview grounded in the returned results · knowledge side panel |
| **Crawler** | PostgreSQL frontier with leases, so there is no separate queue service · fail-closed SSRF checks with IP pinning · robots.txt and a per-host politeness gap · capped exponential retry backoff and expired-lease recovery · HTML, sitemap, RSS/Atom and JSON API ingestion · content fingerprinting for duplicates |
| **Indexer** | Work is derived from freshness, with no second queue · two weighted `tsvector`s per document (text and code) · versioned index format for safe reindexing · vocabulary kept consistent through a transactional outbox · sharded workers |
| **Public API** | Rate limiting, a concurrency cap and per-statement and per-request deadlines · a closed browser tab cancels its query inside PostgreSQL |
| **Admin dashboard** | Crawler, frontier, indexer, corpus, database and search-quality views behind GitHub sign-in |
| **Operations** | One-command Docker Compose deployment with Caddy TLS · backup script and restore test · slow-search log with time per stage |

## Engineering by the numbers

Counts are from `main` as of November 2026. Measurements are from local benchmark runs, and each one links to its record.

| | |
|---|---|
| **57** decision records (ADR) | Why each part is built the way it is, and which alternatives were rejected |
| **23** incident reports (INC) | What broke, the root cause and the fix |
| **17** experiments (EXP) | Questions answered by measuring instead of guessing |
| **805** named test cases in **104** test files | Backend, crawler, indexer and frontend, run in CI against PostgreSQL 16 |

A few results from those records:

- **Indexing went from about 60 to 581 documents per second.** A global vocabulary lock held throughput at 56 to 66 docs/s however many workers ran. Replacing it with an outbox gave 150 to 161, and four shards gave 581, with zero wrong counts. ([EXP-0008](0_tech_docs/infra/performance-and-scaling/EXP-0008-crawl-index-search-at-2m.md), [ADR-0043](0_tech_docs/indexer/vocubulary/ADR-0043-vocabulary-outbox.md))
- **Slow searches went from seconds to milliseconds.** At about 100k documents, common terms pushed PostgreSQL into a sequential scan that read every stored vector. Counting through the GIN index instead was 17 to 68 times faster, and whole cold searches fell from 1.07–1.97 s to 61–275 ms. ([INC-0041](0_tech_docs/backend/bm25-statistics/INC-0041-search-latency-from-detoasting-df-counts.md), [EXP-0016](0_tech_docs/backend/bm25-statistics/EXP-0016-gin-only-document-frequency-counts.md))
- **A title channel recovered 8 of 10 recall misses**, where the right page never reached the candidate pool. ([EXP-0017](0_tech_docs/backend/retrieval/EXP-0017-title-channel-and-dotted-identifier-recall.md))
- **Workers survive a database restart.** Crawler and indexer were tested through a real PostgreSQL outage and through racing writers, ending with 0 of 267,035 vocabulary terms differing from a full recount. ([EXP-0011](0_tech_docs/crawler/worker-runtime/EXP-0011-database-outage-and-concurrent-writers.md))

## Why Developer's Eye?

I never imagined that a homework assignment from fourth grade would one day lead me to build a search engine.

Back in Bangladesh, our teacher gave us homework to memorize the names of search engines. I still remember sitting there repeating **"Google, Yahoo, Pipilika... Google, Yahoo, Pipilika..."** until it stuck. I was a curious kid, so I looked Pipilika up myself, amazed that Bangladesh had a search engine of its own.

Years went by. I grew up, started coding, and almost forgot about it. Then one day a thought crossed my mind: *I wonder how Pipilika is doing these days?*

I looked it up and found that it had shut down after struggling with funding and traffic. Something I remembered so clearly from childhood was now a piece of history.

That led to another thought: **what if I built a search engine myself, right here at home?**

At first the idea seemed almost ridiculous. A whole search engine, with crawlers, indexers, ranking and databases? But I started studying how Google, Bing, Yahoo and open-source projects like Mwmbl were designed. The more I learned, the more that impossible project turned into a series of problems I could actually solve.

That's how Developer's Eye began.

## Architecture

Three processes share one PostgreSQL database and never call each other directly. The crawler writes documents, the indexer notices which documents are new or stale, and the API reads the index.

```mermaid
flowchart LR
  Browser["Browser"] --> Next["Next.js<br/>server routes"]
  Next --> API["FastAPI<br/>search + admin API"]
  API --> DB[("PostgreSQL")]

  subgraph Ingestion
    direction TB
    Frontier["URL frontier<br/>leases, retries, scope"] --> Policy["Host, DNS, robots<br/>and politeness checks"]
    Policy --> Fetch["Bounded fetch"]
    Fetch --> Parse["Parse, normalize,<br/>fingerprint"]
  end

  Parse --> DB
  DB --> Frontier
  DB --> Indexer["Indexer<br/>text + code vectors,<br/>vocabulary"]
  Indexer --> DB
```

A search request goes through these stages in `backend/src/backend/search`:

```
query analysis → planning → retrieval (text + code + title) → merge → BM25 ranking → snippets
```

Only the Next.js app is exposed to the internet. FastAPI is reachable only from the web server and the workers. The full picture is in [architecture.md](0_tech_docs/infra/system-architecture/architecture.md).

## Tech stack

**Frontend**

![Next.js](https://img.shields.io/badge/Next.js_16-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React_19-20232A?style=flat-square&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS_4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)
![GSAP](https://img.shields.io/badge/GSAP-0AE448?style=flat-square&logo=greensock&logoColor=black)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=flat-square&logo=threedotjs&logoColor=white)

**Backend**

![Python](https://img.shields.io/badge/Python_3.14-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-6BA81E?style=flat-square)
![Poetry](https://img.shields.io/badge/Poetry-60A5FA?style=flat-square&logo=poetry&logoColor=white)

**Crawler and indexer**

![Python](https://img.shields.io/badge/Python_3.14-3776AB?style=flat-square&logo=python&logoColor=white)
![HTTPX](https://img.shields.io/badge/HTTPX-2F2F2F?style=flat-square)
![lxml](https://img.shields.io/badge/lxml_+_BeautifulSoup-2F2F2F?style=flat-square)
![asyncpg](https://img.shields.io/badge/asyncpg-2F2F2F?style=flat-square)

**Testing and operations**

![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![Docker](https://img.shields.io/badge/Docker_Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Caddy](https://img.shields.io/badge/Caddy-1F88C0?style=flat-square&logo=caddy&logoColor=white)

## Live demo and local version

### Online: a small prototype

[`developers-eye.vercel.app`](https://developers-eye.vercel.app) runs on a free tier to keep costs at zero: about 100k documents, with one crawler worker and one indexer worker on an Oracle Always Free instance. Running it as a full-scale search engine would cost more than $300 a month, so the hosted version is a prototype of what the code can do, not the limit of it.

![Live preview](assets/live-preview.png)

### Local: the real thing

The open-source version is the main one. Run it on your own hardware with as many crawler and indexer workers as it can handle, and keep the data yourself.

**Want your own search engine instead?** Fork the repo and swap the frontend for your brand. Every endpoint is documented in the generated [API map](0_tech_docs/infra/system-architecture/api-map.md), so you can keep the API as it is and connect your own UI.

![Developer's Eye running locally](assets/local-preview-.png)


![Crawler workers, the indexer and the admin dashboard running side by side in Wave Terminal](assets/local-wave.png)

The [setup guide](setup-guide.md) walks through running a local instance like this one, with as many workers as your machine can take.


## Admin dashboard

**Your whole search infrastructure, visible from one place.**

![Developer's Eye admin dashboard](assets/admin-preview.png)

- **Crawler monitoring:** active workers, live crawl throughput, fetch success rates, p50/p95 fetch latency and pipeline activity.
- **URL frontier and error inspector:** queued URLs, retries, expired leases, blocked requests, HTTP failures and the crawl history of any single document.
- **Indexer monitoring:** indexing throughput, pending documents, stale indexes, worker activity and vocabulary statistics.
- **Corpus analytics:** document counts, source distribution, content freshness, BM25 corpus statistics and storage use.
- **Search quality lab:** slow searches broken down by pipeline stage, BM25 compared with PostgreSQL's ranking, and manual relevance grading scored as P@10, MRR@10 and nDCG@10.
- **Database and system health:** disk use, PostgreSQL connections, table sizes and progress toward corpus-size targets.

**Access:** [online dashboard](https://developers-eye.vercel.app/admin) · local: `http://localhost:3000/admin`

The dashboard is read-only and has no start, stop or delete controls. It needs GitHub sign-in and a connected backend, and it shows data for whichever environment the admin API points at.

## Repository tour

The repo is a monorepo with a strict split: **why** something was built lives in `0_tech_docs/`, and **how** it works lives next to the code.

| Path | What's inside |
|---|---|
| [`backend/`](backend/README.md) | FastAPI app, database models and Alembic migrations. The search engine itself is in `backend/src/backend/search` (query analysis, retrieval, ranking, snippets, evaluation). |
| [`crawler/`](crawler/src/crawler/README.md) | Two Python packages: `crawler` (frontier, policy, fetcher, parser, writer, worker) and [`indexer`](crawler/src/indexer/README.md) (analysis, vectors, vocabulary, worker). Each component has its own `docs/` folder. |
| [`frontend/`](frontend/README.md) | Next.js search UI, API proxy routes and the admin dashboard. |
| [`deploy/`](deploy/README.md) | Docker Compose stack, Caddy config, PostgreSQL settings, backup and restore-test scripts. |
| [`0_tech_docs/`](0_tech_docs/README.md) | Every decision, incident and experiment, grouped by area and feature. Start with its README and the [record index](0_tech_docs/record-index.md). |
| [`0_tech_docs/journal/`](0_tech_docs/journal/README.md) | Build checklists, problems faced, fix logs, test reports and a glossary of terms. |
| [`scripts/`](scripts) | One-command test runner and the generators that keep the docs in step with the code. |
| [`tests/`](tests/test-index-of-whole-app.md) | Index of every test file in the repo, plus a write-up of what each test case checks. |
| `CORE_TRADEOFFS.md` | The core trade-offs behind the engine and what was measured for each, updated with every release. |
| [`technical_handoff.md`](technical_handoff.md) | One file that explains the project end to end. Paste it into your AI assistant to get it up to speed. |

### Three kinds of record

| Prefix | Meaning | Example |
|---|---|---|
| `ADR-XXXX` | A decision, with the options that were rejected | [ADR-0004: PostgreSQL frontier as a job queue with leases](0_tech_docs/crawler/scheduler-and-leases/ADR-0004-postgres-frontier-as-job-queue-with-leases.md) |
| `INC-XXXX` | An incident: what broke, the root cause and the fix | [INC-0013: BM25 ranking corrupted by double stemming](0_tech_docs/backend/bm25-statistics/INC-0013-BM25-ranking-corruption-caused-by-double-stemming.md) |
| `EXP-XXXX` | An experiment: a question, a method and measured results | [EXP-0001: claim path latency with many workers](0_tech_docs/crawler/scheduler-and-leases/EXP-0001-claim-path-concurrency-benchmark.md) |

New records start from the [templates](0_tech_docs/_templates).

### Docs that cannot go stale

These files are generated from the code, and each generator has a `--check` mode that fails when its output is out of date:

| Script | Keeps current |
|---|---|
| `scripts/update_api_map.py` | The [API map](0_tech_docs/infra/system-architecture/api-map.md): every endpoint, who can reach it, and which frontend call hits which backend route |
| `scripts/update_record_index.py` | The [index of all ADRs, incidents and experiments](0_tech_docs/record-index.md) |
| `scripts/update_docs_nav.py` | The documentation map at the end of every README |
| `scripts/update_test_index.py` | The [test index](tests/test-index-of-whole-app.md) and the [list of every test case](tests/all-test-cases-that-were-tested/index.md) |

## Quick start

**You need:** Python 3.14, [Poetry](https://python-poetry.org/), Node.js 24 and PostgreSQL 16 or newer.

Each numbered step runs in its own terminal, from the repository root.

**1. Clone and create two databases**

```bash
git clone https://github.com/nishchup489-afk/developers_eye.git
cd developers_eye

createdb developers_eye
createdb developers_eye_test   # the name must contain "test"
```

**2. Backend**

```bash
cd backend
cp .env.example .env           # set DATABASE_URL and CRAWLER_REPORT_API_KEY
poetry install
poetry run alembic -c alembic.ini upgrade head
poetry run uvicorn backend.main:app --reload
```

**3. Crawler**

```bash
cd crawler
poetry install
poetry run python -m crawler.main bootstrap                        # register sources, queue start URLs
poetry run python -m crawler.worker.runner --forever --concurrency 2
```

**4. Indexer**

```bash
cd crawler
poetry run python -m indexer.worker.runner --forever --batch-size 100 --concurrency 2 --poll-seconds 10
```

**5. Frontend**

```bash
cd frontend
cp .env.example .env.local     # BACKEND_URL=http://127.0.0.1:8000
npm ci
npm run dev
```

Open <http://localhost:3000>. Results appear once the crawler and indexer have processed some pages.

> **Just want to see the UI?** Run step 5 only, with `BACKEND_URL` commented out. The frontend starts in a labeled demo mode with sample data and needs no database.

**6. Tests**

```bash
cp .env.local.example .env.local     # set TEST_DATABASE_URL
python scripts/run_all_tests.py      # every suite, one report
```

For hardware recommendations, running several crawler workers and troubleshooting, see the full [setup guide](setup-guide.md). More detail for each part is in the [backend](backend/README.md), [crawler](crawler/src/crawler/README.md), [indexer](crawler/src/indexer/operations.md) and [frontend](frontend/README.md) guides. To run everything on one server with Docker Compose, follow the [deployment guide](deploy/README.md).

## Environment files

Each part has an example file with comments. Copy it and fill it in. None of the copies are committed.

| File to create | Copy from | Main settings |
|---|---|---|
| `backend/.env` | `backend/.env.example` | `DATABASE_URL` (for example `postgresql+asyncpg://user:password@127.0.0.1:5432/developers_eye`) · `CRAWLER_REPORT_API_KEY` (random, 32+ characters) · optional `GROQ_API_KEY` for the AI overview · optional search limits |
| `frontend/.env.local` | `frontend/.env.example` | `BACKEND_URL` · for the admin dashboard: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `ADMIN_GITHUB_IDS`, `ADMIN_SESSION_SECRET` · `CRAWLER_REPORT_API_KEY` (the same value as the backend) |
| `.env.local` (repo root) | `.env.local.example` | `TEST_DATABASE_URL`, read by both pytest projects and the test runner |
| `deploy/.env` | `deploy/.env.example` | Domain, database password and secrets for the Docker Compose stack |

The admin dashboard signs in through a GitHub OAuth App with the callback `http://localhost:3000/api/auth/github/callback`. Access is limited to the numeric GitHub user IDs you list.

## Testing and evaluation

```bash
python scripts/run_all_tests.py                  # Python suites and fast frontend checks
python scripts/run_all_tests.py --with-build     # also `next build` and the tests that need it
python scripts/run_all_tests.py --only backend indexer
python scripts/run_all_tests.py --save           # write HTML, text and JSON reports
```

![Every test suite passing](assets/test-pass.png)

| Suite | Test files | Named cases | Run it alone |
|---|---:|---:|---|
| Backend (API, search, ranking) | 42 | 358 | `cd backend && poetry run pytest` |
| Crawler | 36 | 338 | `cd crawler && poetry run pytest tests/crawler` |
| Indexer | 14 | 109 | `cd crawler && poetry run pytest tests/indexer` |
| Frontend and admin | 12 | script-style | npm scripts in `frontend/package.json` |



CI runs on every push and pull request: migrations on an empty PostgreSQL 16 database (up, down one, up again), all Python suites, a dependency audit, then lint, type check, build and tests for the frontend. A separate workflow scans for committed secrets.

**Search quality is measured, not assumed.** The backend has an evaluation harness that pools results from both rankers and scores them with P@10, MRR@10 and nDCG@10 from human relevance grades entered in the admin dashboard. Golden-file tests pin BM25 scores and ordering so a ranking change cannot slip in unnoticed.

## Where it stands

This project documents what is unfinished as carefully as what works.

- **Relevance:** on a 25-query baseline, BM25 and PostgreSQL's built-in ranking each win on different metrics, and those grades came from an AI agent. The human-graded run is in progress, so "BM25 is better" is not yet a claim this repo makes. ([EXP-0014](0_tech_docs/backend/ranking/EXP-0014-agent-reviewed-25-query-baseline.md), [EXP-0012](0_tech_docs/backend/ranking/EXP-0012-judged-lexical-relevance-evaluation.md))
- **Load:** search latency under many concurrent users, and during a running crawl, has been planned but not measured. ([EXP-0005](0_tech_docs/infra/performance-and-scaling/EXP-0005-search-and-ingestion-capacity-baseline.md))
- **End-to-end tests:** unit and integration coverage is broad, but full-app tests are not written yet.
- **Scale:** measured up to about 126k documents. The 2M-document target is a plan with estimates, not a result.

### Roadmap

- Version-aware results, so you get the docs for the version you actually use
- A distributed crawler, where anyone can crawl a share of the web and contribute it to a common index
- A hosted documentation site and an engineering blog
- A guide to building a niche search engine on this codebase

## Contributing

Developer's Eye is not only about search. It is also about making the engineering behind a search engine open to other developers.

**The code didn't fall from the sky. There is a reason, an experiment or a lesson behind almost every major decision**, and you can read all of them.

Whether you are new to open source or interested in search infrastructure, you are welcome here.

1. Pick a [`good first issue`](https://github.com/nishchup489-afk/developers_eye/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22), or open a new issue to discuss your idea.
2. Set up a local copy with the [setup guide](setup-guide.md), then read [CONTRIBUTING.md](CONTRIBUTING.md). Contributions are expected to follow it so the repo stays disciplined.
3. Before changing a subsystem, read its overview and decision records in `0_tech_docs/`. If your change alters behavior, add a record for it.

Found a bug? [Open an issue](https://github.com/nishchup489-afk/developers_eye/issues). Have a question or an idea? Come talk on [Discord](https://discord.gg/jxbRsFj3d).

## License and acknowledgments

Released under the [MIT License](LICENSE).

- **Pipilika**, the Bangladeshi search engine that started all of this.
- **[Mwmbl](https://github.com/mwmbl/mwmbl)** and the engineers who have written publicly about how search engines work.
- **PostgreSQL**, which turned out to be capable of far more than a database is usually asked to do.

---

<div align="center">

If this project taught you something or saved you time, a ⭐ helps other developers find it.

</div>