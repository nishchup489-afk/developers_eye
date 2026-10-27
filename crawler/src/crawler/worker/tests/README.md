# Running the worker tests

What each test checks is in [test_case.md](test_case.md).

## Offline pytest suites

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/worker/tests -q -rs --ignore=crawler/src/crawler/worker/tests/test_live_pipeline.py
```

`test_availability.py`, `test_deadlock_retry.py`, `test_monitoring.py`, and `test_recovery.py` use fake sessions and mocks. `test_postgres_pipeline.py` is skipped unless `TEST_DATABASE_URL` is set, and `-rs` shows that skip.

## PostgreSQL pipeline tests

`test_postgres_pipeline.py` needs a dedicated, migrated test database. The URL must use `postgresql+asyncpg` and the database name must contain `test`, or the tests fail on purpose. Each test creates its own source and deletes its rows afterwards.

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:55438/developers_eye_ingestion_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
.\crawler\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/worker/tests/test_postgres_pipeline.py -q
```

The [crawler/tests README](../../../../tests/README.md) has more on setting up this database.

## Live pipeline (real internet)

`test_live_pipeline.py` is a script, not a pytest test. It fetches real pages through the policy coordinator, parses and processes them, and prints the results. It needs `DATABASE_URL` for the robots cache, rolls the session back, and stores nothing.

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.worker.tests.test_live_pipeline
```

By default it fetches five `docs.python.org` pages. To test other pages, pass each URL and its host explicitly:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.worker.tests.test_live_pipeline --allow-host docs.python.org --url https://docs.python.org/3/tutorial/
```

It exits `0` only if at least one document was accepted with no errors.
