# Setup guide

This guide takes you from a fresh clone to a running local search engine: the
API, the frontend, as many crawler workers as your machine can handle, an
indexer, and the admin dashboard to watch it all. The short version lives in the
[README quick start](README.md#quick-start); this is the long one.

Every command runs from the repository root unless a step says otherwise.

## 1. The stack

| Part | Built with | Where |
|---|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 | `frontend/` |
| API | Python 3.14, FastAPI, SQLAlchemy 2, Alembic | `backend/` |
| Crawler and indexer | Python 3.14, HTTPX, lxml + BeautifulSoup, asyncpg | `crawler/` |
| Database | PostgreSQL 16 or newer | one database shared by everything |
| Tests | pytest, npm scripts, GitHub Actions | `scripts/run_all_tests.py` runs all of it |
| Deployment (optional) | Docker Compose, Caddy | `deploy/` |

There is no queue service, search library or vector database to install. The
crawler, indexer and API only talk to each other through PostgreSQL.

## 2. Recommended hardware

The engine runs on a laptop. More cores let you run more crawler and indexer
workers; more RAM and a fast disk keep searches quick as the corpus grows.

| | Minimum (try it out) | Recommended (a real local index) |
|---|---|---|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 to 32 GB |
| Disk | 10 GB free, SSD | 50 GB+ free on NVMe |
| Network | Any stable connection | A fast, unmetered connection for long crawls |

For reference, the numbers in [CORE_TRADEOFFS.md](CORE_TRADEOFFS.md) were
measured on an Intel Core Ultra 7 265F (20 cores) with 32 GB RAM and an NVMe SSD.
The search index grows by about **12 MB per 1,000 documents**, so 100k documents
is roughly 1.2 GB and 2M documents is roughly 23 GB, before PostgreSQL overhead.
The hosted demo runs about 100k documents on a 4-core ARM VM with 24 GB RAM.

## 3. Recommended software

**Required**

- [Python 3.14](https://www.python.org/downloads/) and [Poetry](https://python-poetry.org/docs/#installation)
- [Node.js 24](https://nodejs.org/) with npm
- [PostgreSQL 16 or newer](https://www.postgresql.org/download/), with `createdb` on your `PATH`
- Git

**Nice to have**

- **[Wave Terminal](https://www.waveterm.dev/)**. You will run many processes at
  once (API, frontend, several crawlers, an indexer). Wave puts them all in one
  window as a grid of terminals, next to a CPU graph and a browser block for the
  admin dashboard. This is how the project is run day to day:

  ![Many crawler workers, the indexer and the admin dashboard in one Wave window](assets/local-wave.png)

- **[Reiatsu](https://github.com/nishchup489-afk/reiatsu)** *(coming soon)*.
- Any plain terminal works too: open one tab per process.

## 4. Get the code and create the databases

```bash
git clone https://github.com/nishchup489-afk/developers_eye.git
cd developers_eye

createdb developers_eye
createdb developers_eye_test   # tests refuse any database whose name lacks "test"
```

## 5. Configure the environment files

Copy each example and fill it in. None of the copies are committed.

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
cp .env.local.example .env.local
```

| File | Set at least |
|---|---|
| `backend/.env` | `DATABASE_URL`, for example `postgresql+asyncpg://user:password@127.0.0.1:5432/developers_eye`, and `CRAWLER_REPORT_API_KEY` (any random string of 32+ characters) |
| `frontend/.env.local` | `BACKEND_URL=http://127.0.0.1:8000` and the same `CRAWLER_REPORT_API_KEY`. For the admin dashboard also `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `ADMIN_GITHUB_IDS` and `ADMIN_SESSION_SECRET` |
| `.env.local` (repo root) | `TEST_DATABASE_URL`, pointing at `developers_eye_test` |

The admin dashboard signs in with a GitHub OAuth App. Create one under GitHub
**Settings → Developer settings → OAuth Apps** with the callback
`http://localhost:3000/api/auth/github/callback`, and put your numeric GitHub
user ID in `ADMIN_GITHUB_IDS`.

## 6. Start the backend

```bash
cd backend
poetry install
poetry run alembic -c alembic.ini upgrade head
poetry run uvicorn backend.main:app --reload
```

The API listens on <http://127.0.0.1:8000>. Leave this terminal running.

## 7. Start the frontend

In a new terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:3000>. Search returns nothing until the crawler and
indexer have done some work.

> **Only want to see the UI?** Comment out `BACKEND_URL` in
> `frontend/.env.local` and run this step alone. The frontend starts in a
> labeled demo mode with sample data and needs no database.

## 8. Start the crawler workers

The first time, install the crawler and register the sources:

```bash
cd crawler
poetry install
poetry run python -m crawler.main bootstrap   # register sources, queue the start URLs
```

Then start a worker:

```bash
cd crawler
poetry run python -m crawler.worker.runner --forever --concurrency 2 --batch-size 20
```

**Start as many workers as you want.** Open another terminal (or another Wave
block) and run the same command again. Workers claim URLs from the PostgreSQL
frontier with leases, so they never fetch the same page twice and you can add or
stop them at any time. Per-host politeness is enforced across all of them.

A good starting point is one worker per two CPU cores. Watch the CPU graph and
the admin dashboard, and add workers while throughput keeps rising.

## 9. Start the indexer

In one more terminal:

```bash
cd crawler
poetry run python -m indexer.worker.runner --forever --batch-size 100 --concurrency 2 --poll-seconds 10
```

One indexer is enough to keep up with several crawlers. If the admin dashboard
shows pending documents piling up, start a second one. Results appear in search
as soon as documents are indexed.

## 10. Monitor from the admin page

Open <http://localhost:3000/admin> and sign in with GitHub. The dashboard is
read-only and shows:

- **Crawler:** active workers, crawl rate, fetch success and latency
- **Indexer:** throughput, pending and stale documents, vocabulary
- **Hosts:** requests per host and any 429/503 throttling
- **System:** database size against your disk budget and progress toward your
  document goal

![Admin hosts page](assets/admin-hosts.png)

If a warning says a worker *stopped without shutting down*, that worker's
terminal crashed or was closed. Its leases expire and other workers pick the URLs
up again; restart it when you are ready.

## 11. Run the tests

There is no `.venv` at the repository root. The test runner and maintenance
scripts can use the crawler's environment, which has every package installed:

```bash
crawler/.venv/Scripts/python.exe scripts/run_all_tests.py   # Windows
crawler/.venv/bin/python scripts/run_all_tests.py           # macOS / Linux
```

If Poetry keeps its environments outside the project on your machine, use
`cd crawler && poetry run python ../scripts/run_all_tests.py` instead.

Useful options:

```bash
python scripts/run_all_tests.py --list                    # what would run
python scripts/run_all_tests.py --only backend indexer    # some suites
python scripts/run_all_tests.py --with-build              # include next build
python scripts/run_all_tests.py --save                    # HTML, text and JSON reports
```

Every existing test case is listed in
[tests/all-test-cases-that-were-tested](tests/all-test-cases-that-were-tested/index.md).
Run the suites before and after a change and compare.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Search always returns zero results | The indexer is not running, or has not caught up. Check the Indexer page in the admin dashboard. |
| `alembic upgrade` fails to connect | `DATABASE_URL` in `backend/.env` is wrong, or PostgreSQL is not running. |
| Tests refuse to start | `TEST_DATABASE_URL` is missing from the root `.env.local`, or its database name lacks `test`. |
| Admin sign-in loops back to the login page | The GitHub OAuth callback URL does not match, or your user ID is not in `ADMIN_GITHUB_IDS`. |
| The frontend shows old pages after you change code | A service worker from another local app on port 3000 is caching files. Unregister it in your browser's dev tools. |
| Hosts show as throttled | Too many workers on too few hosts. The crawler backs off by itself; add more sources or fewer workers. |

## Going further

- Run everything on one server with Docker Compose: [deploy/README.md](deploy/README.md)
- Component guides: [backend](backend/README.md), [crawler](crawler/src/crawler/README.md), [indexer](crawler/src/indexer/operations.md), [frontend](frontend/README.md)
- Why it is built this way: [0_tech_docs](0_tech_docs/README.md)
- Ready to change something? Read [CONTRIBUTING.md](CONTRIBUTING.md)
