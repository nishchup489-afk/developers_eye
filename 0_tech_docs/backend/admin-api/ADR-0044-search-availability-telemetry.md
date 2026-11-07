---
id: ADR-0044
title: Record search outcomes per minute in PostgreSQL, and sample the corpus for statistics
status: accepted
date: 2026-11-06
area: backend
feature: admin-api
code:
  - backend/src/backend/search/telemetry.py
  - backend/src/backend/admin_services/search_reporting.py
  - backend/src/backend/admin_services/corpus_reporting.py
  - backend/alembic/versions/d4f1a7c2e9b3_search_minute.py
supersedes:
superseded_by:
related: [ADR-0030, ADR-0037]
---

# ADR-0044: Record search outcomes per minute in PostgreSQL, and sample the corpus for statistics

## TL;DR
Each API process counts search outcomes per minute in memory and upserts them to `search_minute` every 15 seconds. The corpus page scales one page sample past 100,000 rows instead of scanning. Both keep the dashboard honest and cheap at 2M documents.

## Context
On 2026-11-06 common-term searches hit the 3 second deadline and returned 503 until VACUUM ANALYZE ran after a migration. Nothing recorded those failures, so they were found by hand. The API runs two uvicorn processes, and an admin request reaches only one of them, so in-process counters would show about half the traffic and reset on restart. The existing reports count `document` directly, which will not stay cheap at 2M documents behind a 15 second proxy timeout.

## Decision
- `SearchTelemetry` counts outcomes per (minute, process) in memory. `/search` only touches memory, so recording adds no database work to a search.
- A background task upserts the changed minutes every 15 seconds. A write replaces the row with the full count, so a retry cannot double count. Rows live for `admin_event_retention_days`.
- If the write fails, minutes stay in memory, capped at 120.
- Availability is successful ÷ (successful + failed). HTTP 422 is excluded, because a bad query is not an outage.
- Latency is a histogram of successful searches, which merges across processes. Percentiles are estimates from it. Fast failures are excluded so that they cannot flatter latency.
- `/admin/system/search` answers during an outage. On a database failure or after 5 seconds it returns `build_offline_report`, marked `partial`, from the memory of the answering process.
- Health also compares `alembic_version` with the shipped head and flags `document` and `search_index` when changes since ANALYZE pass 20% of rows, because these caused the incident.
- `/admin/system/corpus` counts exactly up to 100,000 rows. Past that it takes totals from planner density times current size, and breakdowns from one TABLESAMPLE SYSTEM pass of about 50,000 rows. The response says which one it used.

## Options considered
- **Per-process memory only.** No migration, but it shows one process and forgets on restart. Rejected because of the two uvicorn processes.
- **One row per search.** Allows query-level detail, but writes on the hot path and stores query text. Rejected.
- **Prometheus.** The usual tool, but it adds a service to a single free-tier server for one page. Rejected for now.
- **Exact corpus counts with a cache.** A cold miss still scans 2M rows, and each process has its own cache. Rejected.

## Trade-offs
- `search_minute` needs a migration. Until it runs the report says so and search keeps working, with one logged warning per outage.
- A hard crash loses up to 15 seconds of counts.
- Sampled breakdowns shift between refreshes and can miss small hosts. The page labels them as estimates.
- The 3 second deadline applies per statement, so the p99 of a multi-statement search can exceed it.

## Enforcement points
- `backend/tests/integration/test_search_reporting.py`
- `backend/tests/unit/test_search_telemetry.py`

## Evidence
Run on 2026-11-06 against a scratch database of 3,000 documents: real `/search` requests appeared on the Availability page within one flush. Query cost on a 2M corpus has not been measured.
