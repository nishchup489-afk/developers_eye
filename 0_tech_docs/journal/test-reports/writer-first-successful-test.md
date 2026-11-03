# Developer's Eye: Database Writer — Debugging & Test Report

**Date:** October 19, 2026  
**Module:** Offline Engine → Database Writer  
**Language:** Python 3.14.4  
**Database:** PostgreSQL + SQLAlchemy 2 (async) + `asyncpg`  
**Testing:** pytest 9.1.1  
**Final result:** **7 PASSED, 0 FAILED — 1.00 second**  
**Status:** Writer integration tests passed. Full crawler integration is still pending.

---

## What did we build and why did we test it?

So far we built the crawler's Source Registry, Seed Discovery, Scheduler, URL Frontier, Policy Coordinator, Fetcher, Parser and Content Processing.

Content Processing gives us a cleaned, classified document with a `content_hash`. **BUT THERE IS A PROBLEM.** A processed document sitting in Python memory isn't useful to a search engine unless we save it somewhere.

That's why we built the **Database Writer**.

Our Writer has two files:

```text
crawler/src/crawler/
└── writer/
    ├── __init__.py
    ├── attempts.py
    ├── documents.py
    └── tests/
        └── test_database_writer.py
```

- **`attempts.py`** records when we tried to crawl a URL and what happened.
- **`documents.py`** inserts a processed document or updates an existing one.

**Worker decides WHAT to execute. Writer decides HOW to save the result.**

We haven't connected the full Worker yet. Before doing that, I wanted to test the actual database operations. Not just mock functions. I wanted to know whether data really gets inserted, updated, and rolled back inside PostgreSQL.

### What we are testing

```mermaid
flowchart TD
    A["Test creates Source + CrawlTarget"] --> B["Writer"]
    B --> C["start_attempt()"]
    B --> D["upsert_document()"]
    C --> E[("crawl_attempt")]
    D --> F[("document")]
    E --> G["Assertions on saved database rows"]
    F --> G
    G --> H["Rollback test data"]
```

This is **Writer-to-database integration testing**, not a real web crawl. No HTTP request, Policy Coordinator, or Worker loop runs in these tests.

---

## 1. First problem — Python couldn't find `crawler.parser`

**Error:**

```text
ModuleNotFoundError: No module named 'crawler.parser'
```

I initially ran the test as:

```powershell
python -m crawler.src.crawler.writer.tests.test_database_writer
```

Our repository uses a `src/` layout:

```text
developers-eye/
├── backend/
│   └── src/
│       └── backend/
└── crawler/
    └── src/
        └── crawler/
            ├── parser/
            ├── processing/
            └── writer/
```

The **actual Python package** is `crawler`, not `crawler.src.crawler`.

For example:

```python
# Correct
from crawler.parser.schemas import ParsedDocument

# Incorrect
from crawler.src.crawler.parser.schemas import ParsedDocument
```

**Fix:** Use the package's installed `src` path and invoke the test with pytest.

From the `crawler/` directory:

```powershell
python -m pytest -v -s src/crawler/writer/tests/test_database_writer.py
```

When troubleshooting imports from the repository root, we also set `PYTHONPATH` to include `crawler/src` and `backend/src`. In a properly installed editable package, that manual setting may not be necessary.

**Result:** The original parser import error was resolved. Pytest moved on to importing the Processing pipeline.

---

## 2. Second problem — `process_document` wasn't exported

**Error:**

```text
ImportError: cannot import name 'process_document' from 'crawler.processing'
```

The test was importing:

```python
from crawler.processing import process_document
```

But Python found this folder:

```text
crawler/src/crawler/processing/
├── __init__.py
├── processing.py
├── schemas.py
├── normalize/
├── classifier/
└── fingerprint.py
```

Our `__init__.py` wasn't exporting the function defined in `processing.py`.

**Fix in `processing/__init__.py`:**

```python
from .processing import process_document, process
from .schemas import (
    ProcessedDocument,
    ProcessingResult,
    SkippedDocument,
)

__all__ = [
    "process_document",
    "process",
    "ProcessedDocument",
    "ProcessingResult",
    "SkippedDocument",
]
```

**Important lesson:** `crawler.processing` is a package. `crawler.processing.processing` is a module inside it. The package can expose functions through `__init__.py` so callers don't have to know the internal file structure.

### Another mismatch in the original test

The original generated test used:

```python
return process_document(parsed, document_type="documentation")
```

But our **real processing function** is:

```python
def process_document(document: ParsedDocument) -> ProcessedDocument | SkippedDocument:
    ...
```

It automatically classifies the document. It doesn't accept `document_type`.

**Correction:**

```python
return process_document(parsed)
```

For integration tests, the result should also be checked to ensure it is a `ProcessedDocument`, not a `SkippedDocument`, before sending it to the Writer.

---

## 3. Third problem — Circular import inside Content Processing

**Error:**

```text
ImportError: cannot import name 'classify_document'
from partially initialized module
'crawler.processing.classifier.classify'
(most likely due to a circular import)
```

After updating `__init__.py`, the import chain revealed another issue:

```text
processing/__init__.py
    ↓
processing/processing.py
    ↓
classifier/classify.py
    ↓
classifier/utility.py
    ↓
crawler.src.crawler.processing.classifier.patterns
    ↓
processing package is loaded under another name
    ↓
CIRCULAR IMPORT
```

In `classifier/utility.py`, an import started with the wrong prefix:

```python
# Wrong
from crawler.src.crawler.processing.classifier.patterns import _TOPIC_PATTERNS
```

**Fix:**

```python
from .patterns import _TOPIC_PATTERNS
```

Or:

```python
from crawler.processing.classifier.patterns import _TOPIC_PATTERNS
```

### We checked the rest of the crawler

PowerShell search:

```powershell
Get-ChildItem crawler/src/crawler -Recurse -Filter *.py |
    Select-String "crawler\.src\.crawler"
```

This found **8 matching import statements**, spread across the Policy Coordinator, normalizer, and test files:

```text
policy_and_politeness/policy_coordinator.py
policy_and_politeness/tests/test_politeness_policy.py
processing/normalize/normalize.py
processing/normalize/utility.py  (2 matches)
processing/tests/test_fingerprint.py  (2 matches)
processing/tests/test_processing.py
```

The incorrect package prefix was changed from `crawler.src.crawler.` to `crawler.` (or replaced with a suitable relative import).

After the import corrections, pytest successfully collected all **7 Writer tests**.

**Lesson:** The filesystem path and the package import path are not the same thing. Don't mix `crawler.processing` with `crawler.src.crawler.processing`.

---

## 4. Fourth problem — Test database URL was missing

**Result:** 7 failed.

**Error:**

```text
Failed: Set TEST_DATABASE_URL to a dedicated PostgreSQL test database.
Do not point this test at your actual crawler database.
```

At this point, our Python imports were working. We finally reached the test's database setup, but the test intentionally refused to run because no test database URL was configured.

Why? Because these tests perform real SQL `INSERT`, `UPDATE`, and `CREATE TABLE IF NOT EXISTS` operations. I don't want a test accidentally modifying our regular Developer's Eye database.

**Fix:** Configure a **dedicated PostgreSQL test database** using the environment variable `TEST_DATABASE_URL`.

Example only — use your actual, private credentials:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/developers_eye_test"
```

The test checks that the database name contains `test` as a safety guard. This guard is useful, but the URL still needs to point to a genuinely separate database.

**Result:** The missing-variable error was resolved. The test progressed to loading the PostgreSQL driver.

---

## 5. Fifth problem — PostgreSQL driver wasn't installed

**Result:** 7 failed.

**Error:**

```text
ModuleNotFoundError: No module named 'asyncpg'
```

We are using **SQLAlchemy AsyncSession**. Our connection URL specifies the `asyncpg` dialect:

```text
postgresql+asyncpg://...
```

SQLAlchemy handles the database queries; `asyncpg` is the asynchronous driver that actually communicates with PostgreSQL.

Without it, SQLAlchemy couldn't even create a working database connection.

**Fix from the `crawler/` directory:**

```powershell
poetry add asyncpg
```

Verify:

```powershell
python -c "import asyncpg; print('ASYNCPG INSTALLED:', asyncpg.__version__)"
```

**Result:** The missing-driver error was resolved. The next failure occurred during PostgreSQL authentication.

---

## 6. Sixth problem — PostgreSQL rejected the password

**Result:** 7 failed.

**Error:**

```text
asyncpg.exceptions.InvalidPasswordError:
password authentication failed for user "postgres"
```

This was actually progress. The driver was installed, and PostgreSQL was responding. But the username/password in `TEST_DATABASE_URL` weren't accepted.

**Fix:** Use the correct credentials for the PostgreSQL instance hosting the dedicated test database. We can validate credentials without running pytest:

```powershell
psql -h localhost -U postgres -d developers_eye_test -W
```

If the password includes special URL characters such as `@`, `#`, or `%`, encode them when building the connection URL.

**Result:** Authentication was corrected. Tests finally ran actual SQL against PostgreSQL.

---

## 7. Seventh problem — 6 passed, 1 failed

**Actual test result:**

```text
6 passed, 1 failed
```

Now the interesting part. **The database connection worked, and 6 real integration tests passed.** Only one assertion was failing.

**Error:**

```text
KeyError: 'code_blocks'
```

The failing test contained:

```python
assert saved.metadata_["code_blocks"]
```

### Why this happened

Our `ProcessedDocument` contains:

```text
canonical_url
document_type
title
description
body
author
content_hash
published_at
headings
code_blocks
tags
metadata
```

But our PostgreSQL `Document` model doesn't have separate columns for `headings`, `code_blocks`, and `tags`. Instead, it has a flexible **JSONB metadata column**.

The Writer was saving `document.metadata`, but it wasn't adding the other structured fields.

**So the data existed after processing, but it wasn't being saved in the expected JSONB structure.**

### Fix in `writer/documents.py`

Before building the INSERT statement:

```python
metadata = {
    **document.metadata,
    "headings": list(document.headings),
    "code_blocks": list(document.code_blocks),
    "tags": list(document.tags),
}
```

Then replace:

```python
metadata_=document.metadata,
```

with:

```python
metadata_=metadata,
```

Our existing PostgreSQL `ON CONFLICT DO UPDATE` already handles metadata updates, so we didn't need another database column or another migration.

Why preserve these fields?

Imagine someone searches **"asyncio Python examples"** on Developer's Eye. The actual code examples and headings can later improve the search experience. We shouldn't throw them away after parsing and processing.

**Result:** The missing `code_blocks` issue was fixed. We ran all 7 tests again.

---

## 8. FINAL SUCCESSFUL TEST RUN

**Command from `crawler/`:**

```powershell
python -m pytest -v -s src/crawler/writer/tests/test_database_writer.py --tb=short
```

**Environment reported by pytest:**

```text
Platform:  win32
Python:    3.14.4
pytest:    9.1.1
pluggy:    1.6.0
anyio:     4.15.1
Root:      crawler/
Tests:     7 collected
```

### Final results (from the actual terminal output)

| # | Test | What it verified | Result |
|---|---|---|---|
| 1 | `test_attempt_starts_and_finishes` | Create an unfinished `crawl_attempt` and finish it with HTTP 200 and 1234 bytes | **PASSED** |
| 2 | `test_attempt_cannot_be_finished_twice` | A completed attempt cannot be overwritten by a second completion | **PASSED** |
| 3 | `test_attempt_validates_inputs` | Reject invalid IDs, HTTP statuses, byte counts, and outcomes | **PASSED** |
| 4 | `test_document_insert_and_unchanged_recrawl` | INSERT a new document; UPSERT identical data without changing document ID or `updated_at`; refresh `last_seen_at` | **PASSED** |
| 5 | `test_changed_content_updates_existing_document` | Changed body/hash updates the existing document rather than inserting a duplicate | **PASSED** |
| 6 | `test_metadata_only_change_counts_as_update` | Metadata changes update the document even when the content hash is unchanged | **PASSED** |
| 7 | `test_writer_respects_worker_transaction_rollback` | Rolling back a transaction removes uncommitted attempt/document writes | **PASSED** |

### Relevant terminal output

```text
test_attempt_starts_and_finishes
  [PASS] started crawl_attempt #5
  [PASS] success / 200 / 1234 bytes recorded
PASSED

test_attempt_cannot_be_finished_twice
  [PASS] duplicate completion rejected; original outcome preserved
PASSED

test_attempt_validates_inputs
  [PASS] invalid inputs rejected
PASSED

test_document_insert_and_unchanged_recrawl
  [PASS] document #7 inserted with correct metadata and hash
  [PASS] same ID; last_seen_at refreshed; updated_at unchanged
PASSED

test_changed_content_updates_existing_document
  [PASS] same ID, changed body/hash and newer updated_at
PASSED

test_metadata_only_change_counts_as_update
  [PASS] metadata-only change detected
PASSED

test_writer_respects_worker_transaction_rollback
  [PASS] uncommitted attempt and document were rolled back
PASSED

========================= 7 passed in 1.00s =========================
```

**Final count: 7 passed / 0 failed.**

---

## 9. What did these tests actually prove?

### A. `start_attempt()` and `finish_attempt()` work

Suppose a Worker claims:

```text
https://docs.python.org/3/tutorial/
```

The Writer can create an unfinished row:

```text
crawl_attempt
---------------------------------
crawl_target_id: 10
started_at: <database timestamp>
finished_at: NULL
outcome: NULL
```

Later, it can finish the same attempt:

```text
http_status: 200
outcome: success
bytes_received: 1234
finished_at: <database timestamp>
```

The tests also verified that a finished attempt cannot be finalized a second time.

### B. Document deduplication works by canonical URL

**First crawl:**

```text
canonical_url does not exist
    ↓
INSERT new document
    ↓
Return document ID
```

**Second crawl, unchanged page:**

```text
canonical_url already exists
    ↓
ON CONFLICT DO UPDATE
    ↓
Same document ID
    ↓
last_seen_at changes
updated_at stays the same
```

**Third crawl, changed content:**

```text
Same canonical URL
    ↓
Different content_hash
    ↓
UPDATE body, hash, and updated_at
    ↓
Still the same document ID
```

This is exactly why we used a **PostgreSQL UPSERT** instead of a regular INSERT.

### C. Metadata-only changes are detected

Content hashes are intentionally derived from searchable content, not every metadata field. A page's metadata can change without its body changing.

The tests verified that we still save those metadata updates.

### D. Database transactions behave correctly

Imagine the Worker starts saving an attempt and document, but then something fails before the transaction commits.

The database must not keep half of that transaction.

Our rollback test verified that **uncommitted Writer operations are rolled back together**.

**Important:** The Writer does not call `commit()` internally. Transaction ownership remains with the caller — eventually our Worker.

---

## 10. Why are the IDs #5 and #7 instead of #1?

In the successful output, the attempt ID was `#5`, and the document ID was `#7`.

This is normal PostgreSQL behavior. Identity/sequence values can advance even when transactions are rolled back. The next inserted row doesn't have to reuse a previous ID.

**IDs identify rows; they are not guaranteed to be gapless counters.**

This doesn't mean duplicate documents were inserted.

---

## 11. Test isolation and limitations

Our test suite uses a dedicated PostgreSQL database, seeds temporary `Source` and `CrawlTarget` records, runs actual SQL, and rolls back each test's data. It may create missing tables in that **test database** using SQLAlchemy model metadata; it does not verify Alembic migrations.

What these results **do prove**:

- Writer imports and database connectivity work in the tested environment.
- Crawl-attempt INSERT and UPDATE work.
- Document INSERT and canonical-URL UPSERT work for the tested scenarios.
- JSONB metadata containing code blocks, headings and tags is saved as expected in the insert test.
- Hash-aware and metadata-aware updates behave as expected.
- The tested rollback behavior works.

What we **haven't proved yet**:

- A real URL can travel through Scheduler → Policy Coordinator → Fetcher → Parser → Processing → Writer.
- Multiple concurrent Workers handle database leases safely.
- Expired leases, network timeouts, robots denials, HTTP 304/429/503, and retries are correctly wired end to end.
- `noindex`, redirects, discovered URLs, and recrawl policies work in the complete pipeline.
- Alembic migrations and production deployment have been validated by this test suite.
- The online Search API or Search Indexer is functioning.

**Conclusion:** The **Database Writer MVP is tested and working**, but the entire offline engine is not yet complete.

---

## 12. Next: Worker integration

Now it's time to connect the components instead of testing them separately.

```mermaid
flowchart TD
    A["Source Registry + Frontier"] --> B["Scheduler claims target"]
    B --> C["Worker: jobs.py"]
    C --> D["Attempt Writer: start_attempt()"]
    C --> E["Policy Coordinator + Fetcher"]
    E --> F["Parser"]
    F --> G["Content Processing"]
    G --> H["Document Writer: upsert_document()"]
    C --> I["Attempt Writer: finish_attempt()"]
    H --> J[("PostgreSQL")]
    D --> J
    I --> J
    C --> K["Scheduler completes / retries target"]
    F --> L["Scope-checked links → Frontier"]
```

**Next files:**

```text
crawler/src/crawler/worker/
├── __init__.py
├── jobs.py       # Execute one leased crawl target
└── runner.py     # Keep claiming and running jobs
```

Our first end-to-end milestone will be simple: start the Worker, crawl a permitted real documentation page, and inspect the resulting rows in `crawl_attempt`, `document`, and `crawl_target`.

---

## Final note

We went from a broken Python import to **7 real database integration tests passing**.

The debugging progression was:

```text
Wrong Python module path
    ↓
Processing function not exported
    ↓
Circular imports from mixed package paths
    ↓
Missing TEST_DATABASE_URL
    ↓
Missing asyncpg driver
    ↓
PostgreSQL password authentication failed
    ↓
6 passed, 1 failed (missing code_blocks in JSONB)
    ↓
Fixed metadata persistence
    ↓
7 PASSED, 0 FAILED — 1.00s
```

The biggest lesson from this stage: **a passing module test is not enough. We need real integration tests to catch the problems between modules, data schemas, and the database.**

**Database Writer: DONE for MVP. Next: Worker.**
