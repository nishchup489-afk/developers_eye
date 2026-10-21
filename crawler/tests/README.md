# Testing Crawler Ingestion

## 1. What are we testing?

So we now have sitemap, RSS/Atom and JSON API ingestion. There are three different questions we need to answer.

Does the parser turn bytes into the right records? Does the worker apply source scope and call the shared processor? Does the finalizer actually commit the expected documents, child targets and finished attempts?

One test layer cannot prove all three.

## 2. Start with the offline ingestion tests

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests -q
```

These tests use literal XML/JSON and test doubles for network and persistence. Worker tests still run the actual parser and content processor. They cover configuration, document identities, scope, pagination, robots headers, malformed input and bounded parsing.

The feed package exposes `parse_feed` through both `crawler.parser.feeds` and `crawler.parser.feeds.rss_atom`. The implementation lives in `feeds/parser.py`.

## 3. Run the existing offline regression suite too

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler backend/tests crawler/tests -q --ignore=crawler/src/crawler/worker/tests/test_live_pipeline.py --ignore=crawler/src/crawler/writer/tests/test_database_writer.py --ignore=crawler/src/crawler/policy_and_politeness/tests/test_dns_policy.py
```

Why those exclusions? The live pipeline is a separate live-crawl tool. Writer tests need a dedicated database. The older DNS file has its own async test runner, so run that runner directly:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.policy_and_politeness.tests.test_dns_policy
```

The PostgreSQL pipeline cases skip when `TEST_DATABASE_URL` is absent. A skipped database test is not evidence that persistence passed.

## 4. Verify real PostgreSQL writes

Create a separate test database, then set both variables for that test process:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:55438/developers_eye_ingestion_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
.\crawler\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/worker/tests/test_postgres_pipeline.py crawler/src/crawler/writer/tests/test_database_writer.py -q
```

The example DSN assumes a dedicated test server already running on port 55438 with matching authentication. It does not start a server or create that database. Set the DSN to your own isolated test database. Its name must contain `test`; the test helpers enforce that condition.

The structured-resource integration cases claim real frontier rows, run actual parsers and processing, and use the real transaction finalizer. HTTP fetches are replaced with deterministic responses. They check stored document metadata, queued page/pagination kinds and depths, finished attempts and document inspection.

The existing concurrency, recovery and writer tests run against the same dedicated test database. They do not use the application's normal crawler database.

## 5. What passed for this implementation?

The final offline run passed 456 tests and 33 subtests. Its six PostgreSQL cases skipped in that offline run. Running the database suite separately against a migrated disposable PostgreSQL 18 instance passed all 13 integration tests. The standalone DNS runner passed all 73 checks.

Python compilation, Poetry's lock validation and the diff whitespace check also passed. The disposable server was stopped after testing. These are deterministic parser/worker/database checks; they do not claim that every external website or API has been crawled successfully.
