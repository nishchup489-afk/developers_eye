---
id: EXP-0013
title: Separate cold DF cost from retrieval expansion and page hydration
status: done
outcome: adopt
date: 2026-11-09
area: infra
feature: performance-and-scaling
informs: [ADR-0038]
---

# EXP-0013: Read-only search stage profiling

## Question

Does loading large candidate metadata before pagination explain search latency,
or does live DF counting dominate cold searches?

## Why it matters

The audited 75 ms / 515 ms / 2.53 s variation mixes different queries and cache
states. Measure SQL stages before adding maintained ranking tables or indexes.

## Setup

Windows 11, Python 3.14.4, PostgreSQL 18.3, 100,141 indexed documents from the
local developer-documentation corpus. Queries run in one repeatable-read,
read-only transaction. No application corpus writes or cache flushes occurred.
Five observations per query/cache variant; p95/p99 are the observed maximum
at this sample size, not production tail estimates. The existing application
may have other clients; this is a local profile, not isolated capacity evidence.

## Method

Six queries cover common text, merged channels, a code identifier, FastAPI,
a source filter, and no matches. Clear only the application DF cache for cold
runs; PostgreSQL and OS caches remain in place. Capture per-query SQL counts,
durations, result URLs, and EXPLAIN ANALYZE/BUFFERS plans. Then project only
tags before paging and fetch code blocks with final-page bodies.

## Reproduce

From repository root, with installed backend dependencies and DATABASE_URL:

```powershell
python scripts/profile_search.py --rounds 5 --output backend/reports/checklist/search-before.json
# Apply the page-hydration change, then repeat with another output path.
python scripts/profile_search.py --rounds 5 --output backend/reports/checklist/search-after-hydration.json
```

Cold means DF-cache-cold, not disk-cold. Increasing rounds improves percentile
resolution. Raw reports retain every sample and plan.

## Results

| Query | Before cold p50 ms | Before warm p50 ms | After warm p50 ms | Warm SQL calls |
| --- | ---: | ---: | ---: | ---: |
| python, text | 2116.068 | 205.482 | 242.796 | 5 |
| python async, all | 999.959 | 133.294 | 127.833 | 7 |
| asyncio.create_task, code | 138.979 | 13.083 | 13.273 | 5 |
| FastAPI Depends, all | 233.969 | 78.558 | 87.190 | 7 |
| fastapi, docs | 42.416 | 48.902 | 59.204 | 5 |
| no match | 2.086 | 1.889 | 2.002 | 2 |

Before-change average SQL-stage cost for `python async`:
DF 878.174 ms cold; TSVECTOR expansion 72.737 ms cold / 69.938 ms warm;
document hydration 30.192 ms cold / 13.482 ms warm. After-change warm hydration
was 5.738 ms, but total timings vary and do not establish a general speedup.

The common `python` DF plan chose a sequential scan (998.509 ms); the rare
code-term DF used the existing code-vector GIN bitmap index (0.766 ms).
Filtered candidates used the existing text GIN index (4.827 ms).
Both channels already have GIN indexes; category has a B-tree index.
The initial corpus-statistics load was 3777.979 ms before / 2563.078 ms after,
which is startup/cache noise rather than an effect of hydration projection.

Raw data: [before](../../../backend/reports/checklist/search-before.json),
[after](../../../backend/reports/checklist/search-after-hydration.json).

## Analysis

Cache state, common-term selectivity, live DF counts, and per-candidate vector
expansion explain much of the earlier variation. Hydrating full JSONB for every
candidate was avoidable work; only final-page code blocks are now loaded.
No rank weights, candidate budgets, or query-matching semantics changed.

## Outcome

Adopt the small projection change and bounded, query-relevant code-block
selection. Keep the existing channel-aware DF cache. Defer persisted TF/DL/DF
tables: these measurements establish read cost but do not establish that the
write amplification, backfill, removal, and reconciliation costs are justified.
Revisit with representative cold-query QPS, cache miss rate, and an ingestion
benchmark before accepting a maintained-statistics design. Do not claim the
cold-common-term deadline problem is solved by this experiment.
