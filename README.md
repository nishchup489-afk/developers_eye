<p align="center">
  <img src="assets/developers-eye-banner.png" alt="Developer's Eye — Search Beyond the Surface" width="100%" />
</p>

<p align="center">
  <strong>Developer-first search infrastructure. Built from the crawler up.</strong><br />
  <sub>Documentation • Technical knowledge • Agent-ready search</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-active%20development-38bdf8?style=flat-square" alt="Active development" />
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.14" />
  <img src="https://img.shields.io/badge/Next.js-16-111827?style=flat-square&logo=nextdotjs" alt="Next.js 16" />
</p>

## The mission

**Developer's Eye** is an independent search engine for developers and coding agents. It crawls developer resources, extracts useful content, and is being built to return **fast, relevant, source-first results** without AI-generated clutter.

`Discover → Crawl → Parse → Persist → Index → Rank → Search`

## Stack

**Crawler:** Python 3.14 · asyncio · HTTPX · Beautiful Soup · lxml  
**Data:** PostgreSQL · SQLAlchemy (async) · Alembic  
**API:** FastAPI · Pydantic  
**Web:** Next.js 16 · React · TypeScript · Tailwind CSS

## Build progress

- [x] Source discovery, frontier scheduling, robots/host policies, and concurrent crawling
- [x] HTML/XML processing, document persistence, and crawler monitoring
- [ ] Search indexing and BM25-style ranking
- [ ] Public search API and end-to-end search experience
- [ ] Agent-facing API / MCP integration

## Run locally

Requires **Python 3.14, Poetry, Node.js, and PostgreSQL**. Create the PostgreSQL database and set `DATABASE_URL` in `backend/.env` before running migrations.

```bash
# Terminal 1 — backend API
cd backend
poetry install
cp .env.example .env
poetry run alembic upgrade head
poetry run uvicorn backend.main:app --reload
```

```bash
# Terminal 2 — crawler (from repository root)
cd crawler
poetry install
poetry run python -m crawler.seed.seed
poetry run python -m crawler.worker.runner --forever
```

```bash
# Terminal 3 — web (from repository root)
cd frontend
npm install
npm run dev
```

**Web:** http://localhost:3000 · **API:** http://127.0.0.1:8000/docs  
Admin features require additional environment configuration; see `frontend/.env.example`.

## Follow the build

Created by **Sadnan Nishthup** · [X / Twitter](https://x.com/Nishchup489) · [LinkedIn](https://www.linkedin.com/in/sadnan-nishthup-7405273a5)  
**Repository:** [nishchup489-afk/developers_eye](https://github.com/nishchup489-afk/developers_eye)
