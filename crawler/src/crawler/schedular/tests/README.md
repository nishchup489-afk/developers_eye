# Running the scheduler tests

What each test checks is in [test_case.md](test_case.md). `test1_report.md` and `image.png` are an earlier run report.

All three files are standalone scripts, not pytest tests. Each one needs PostgreSQL through the backend's `DATABASE_URL`, with migrations applied. They create a uniquely named temporary source and targets inside one transaction and roll it back, so nothing is left behind. Still, point them at a development or test database, never production.

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.schedular.tests.test_repository
.\crawler\.venv\Scripts\python.exe -m crawler.schedular.tests.test_complete_target
.\crawler\.venv\Scripts\python.exe -m crawler.schedular.tests.test_fail_target
```

Each prints PASS lines and a final success message, then `Test transaction rolled back`. A failed check prints FAIL and raises.

On Windows the scripts switch to a selector event loop themselves, which asyncpg needs.
