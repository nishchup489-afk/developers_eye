# Developer's Eye backend

Python 3.14 and Poetry are required. From the repository root:

```powershell
cd backend
poetry install
poetry run alembic -c alembic.ini upgrade head
poetry run uvicorn backend.main:app --reload
```

Configure `DATABASE_URL` and a random `CRAWLER_REPORT_API_KEY` of at least 32 characters in `backend/.env`. The frontend uses the same reporting key on its server.

In another terminal, from the repository root:

```powershell
cd crawler
poetry install
poetry run python -m crawler.main bootstrap
poetry run python -m crawler.worker.runner --forever --concurrency 2
```

The crawler has a relative dependency on `../backend`. Reporting reads live in `backend.services`; the backend has no crawler dependency. No custom `PYTHONPATH` is needed after installation.

Apply migrations before restarting workers after a schema update. Source configuration supports `max_depth` (default 3), `max_pages` (default 10000), and optional `allowed_path_prefixes` (default all paths on approved hosts). Counts include existing frontier URLs.

Read-only report CLI:

```powershell
poetry run python -m crawler.worker.reporting --days 7
```

Run the report command from the crawler environment.
