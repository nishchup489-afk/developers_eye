# Running the frontier tests

What each test checks is in [test_case.md](test_case.md).

## Pytest (no database)

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/frontier/tests -q
```

This runs `test_urls.py` and `test_scope.py`. Both use fake sessions, so no database is needed.

## Database script

`test_enqueue_target.py` is a script, not a pytest test (it has no `test_` function). It needs a PostgreSQL database reachable through the backend's `DATABASE_URL`, with at least one enabled source (run the source seeder first). It rolls its insert back.

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.frontier.tests.test_enqueue_target
```

It prints `TEST PASSED` on success.
