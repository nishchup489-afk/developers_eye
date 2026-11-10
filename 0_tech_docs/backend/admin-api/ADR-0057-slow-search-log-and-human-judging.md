---
id: ADR-0057
title: Log slow searches with stage timings and store human relevance judgments in PostgreSQL
status: accepted
date: 2026-11-10
area: backend
feature: admin-api
code: [backend/src/backend/search/trace.py, backend/src/backend/search/telemetry.py:record_slow, backend/src/backend/models/search_quality.py, backend/src/backend/admin_services/search_quality.py, backend/src/backend/api/search_quality.py, frontend/components/admin/search-quality.tsx]
supersedes:
superseded_by:
related: [ADR-0044, ADR-0030, EXP-0012, EXP-0014, INC-0041]
---

# ADR-0057: Slow-search log and human relevance judging

## TL;DR
Searches at or over `SEARCH_SLOW_QUERY_MS` (default 1000 ms) and every timeout are stored one row each,
with time per stage (retrieval, ranking, metadata, snippets). Human 0–3 grades for a fixed query set are
stored in PostgreSQL and turned into BM25 and PostgreSQL P@k, MRR@k and nDCG@k on the admin
Search quality page. Agreement between the two rankers is not evidence of relevance; only human grades are.

## Context
INC-0041 took a 100k offline run to find, because ADR-0044 keeps only per-minute counts and no query-level
detail. Ranking work also lacked human judgments: EXP-0014 grades were made by an agent and cannot
establish that results got better.

## Decision
- `search/trace.py` keeps a per-request trace in a `ContextVar`; `service.py` wraps each stage. On
  success or timeout, `telemetry.record_slow` keeps the search only if it timed out or took at least the
  threshold. Rows are buffered in memory (at most 200) and written by the existing telemetry flush into
  `search_slow_query`, pruned with the same retention. Query text is cut to 256 characters.
- Judging tables: `relevance_query` (id, query, mode, source, stratum, note, `no_relevant_documents`),
  `relevance_run` (each pool capture: both rankers' top results with their positions) and
  `relevance_judgment` (query, URL, grade 0–3 or null, note, origin `pool` or `added`, judge, time).
- A pool is the union of the top 10 from BM25 and from PostgreSQL `ts_rank_cd` over the production
  candidates. Re-pooling keeps grades. Pages are shown alphabetically without ranks, so position cannot
  bias a grade. A judge may add a page neither ranker found (origin `added`).
- A query counts as complete only with a pool and at least one positive grade, or the "no relevant page"
  flag. Aggregates are means over complete queries only, and the page says when they are provisional.
- API: `/admin/search-quality/*` behind the report key. The Next.js routes let viewers read; writes need an
  administrator session and a same-origin `Origin` header, and the judge is the session login, never a
  client field. Slow-search query text is shown to administrators only.
- The 36-query set ships inside the backend package (`search/evaluation/human_judging_queries.json`) so it
  is present in the Docker image; EXP-0014 agent grades are deliberately not imported.

## Options considered
| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Row per slow search only, judgments in PostgreSQL | Query-level detail where it matters; tiny write volume; judgments survive restarts and are shared | Stores some query text | chosen |
| B. Row per search (all searches) | Full distribution | Writes on the hot path for every search; stores all query text (ADR-0044 rejected this) | rejected |
| C. Logs only | No schema | Two processes, no stage summary, lost on restart | rejected |
| D. Judgments in JSON files in git | Reviewable diffs | Needs a developer to grade; no UI for the owner | rejected for now; export can come later |

## Why
Slow searches are rare by definition, so one row each is cheap and gives exactly the stage evidence that
INC-0041 lacked. This narrows ADR-0044's "no row per search" rule rather than reversing it: only slow or
timed-out searches are stored, text is capped and admin-only, and retention is the same.

## Consequences
- Gained: per-stage evidence for slow searches; a repeatable human-judged comparison of the two rankers.
- Accepted limitations: metrics are only as good as the number of judged queries; stored query text needs
  the same care as other telemetry.
- Depends on this: the admin Search quality page; future ranking ADRs should cite its metrics.

## Invariants
- Only searches at or over the threshold, or timed out, are stored; nothing else from the hot path writes rows.
- Writes to judgments require an administrator; viewers never see slow-search query text.
- The judging view never shows ranker positions.

## Evidence
- Tests: `tests/integration/test_search_quality.py`, `tests/api/test_search_quality_routes.py`,
  `tests/unit/test_search_trace.py`; frontend `tests/search-quality-unit.mjs` and the search-quality block
  in `tests/admin-routes.mjs`.
- Measured: page checked against the 42k database with a real grade saved through the UI.

## Revisit when
- More than about 1,000 slow searches a day (threshold too low or a real regression).
- A second judge joins (add agreement statistics) or the set grows past about 100 queries.

## Rules for future changes
- Do not store every search without a new ADR that supersedes ADR-0044 and this one.
- Do not show ranker positions in the judging view.
- Regression tests above must keep passing.
