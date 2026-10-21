# Verifying the fixes against PostgreSQL

**Files involved:** `worker/tests/test_postgres_pipeline.py` and the existing database-writer tests.

## The problem

Offline mocks cannot prove PostgreSQL locking, concurrent budgets, transaction commits or index invalidation. These paths needed dedicated database regression coverage.

## What changed

Add tests that require an explicitly configured, migrated test database. Each test creates an isolated source and cleans up its own rows. HTTP fetching is mocked; PostgreSQL claims, attempts, document writes, budgets and reporting queries are real.

## Verification

- Concurrent claims do not overlap.
- Concurrent finalization respects a shared seven-URL source budget.
- Documents and finished attempts commit together.
- A 404 removes the search entry while preserving the document, and a later 200 restores availability.
- Expired claims receive backoff; an old worker cannot alter a newer claim.
- Monitoring reads persisted documents and inspection content.

Run after applying migrations to a dedicated database, from `crawler/`:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://USER:PASSWORD@localhost/developers_eye_test"
poetry run pytest src/crawler/writer/tests/test_database_writer.py src/crawler/worker/tests/test_postgres_pipeline.py -q
```

The database name must contain `test`. No live website is crawled by these tests.

Verified locally: all migrations applied to a disposable PostgreSQL 18 database; 10 writer/pipeline integration tests passed. The combined offline suite passed 400 tests and 33 subtests with no expected failures. Frontend lint, TypeScript, admin contracts, both Poetry lock checks and both wheel builds passed. Async tests used a selector loop without a Windows wakeup socket in this execution environment.
