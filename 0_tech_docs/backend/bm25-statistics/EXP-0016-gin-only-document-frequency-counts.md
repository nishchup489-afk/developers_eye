---
id: EXP-0016
title: GIN-only document-frequency counts against the planner's seq-scan choice at 126k documents
status: done
outcome: adopt
date: 2026-11-10
area: backend
feature: bm25-statistics
informs: [INC-0041, ADR-0027]
---

# EXP-0016: GIN-only document-frequency counts

## Question
Forcing BM25 document-frequency counts onto the GIN index keeps them under 100 ms per query at about
126k documents, with identical counts, where the sequential-scan plan takes over 900 ms.

## Why it matters
INC-0041: DF counts held most of the 5–11 s search times seen at 100k documents.

## Setup
- Hardware / OS: cloud Linux container, PostgreSQL 16, shared_buffers 512 MB, work_mem 32 MB.
- Data: the 8 Nov dump (42,114 documents) scaled to about 126k by copying each document twice with new
  ids, so term frequencies are realistic but every document appears three times.
- Configuration: production `search_index` vectors and GIN indexes, warm cache.

## Method
- Baseline: the same DF SQL with bitmap and index scans disabled (the plan PostgreSQL 18 chose on the user's 100k corpus).
- Variable changed: the shipped `_get_document_frequencies` (seq scans disabled for that statement).
- Metrics: wall time for all of a query's DF counts (both channels in `all` mode); counts compared per term.
- Queries: the nine slow queries from the 100k run.

## Reproduce
```
PYTHONPATH=backend/src DATABASE_URL=postgresql+asyncpg://... python backend/evaluation/exp-0016/dfbench.py out.json
```
Raw results: `backend/evaluation/exp-0016/df-126k-results.json`.

## Results
| Query | Mode | Seq-scan plan (ms) | GIN plan (ms) |
| --- | --- | ---: | ---: |
| python generator yield from | all | 1653.8 | 56.3 |
| python dataclasses | text | 971.6 | 17.9 |
| python context manager | all | 1347.7 | 53.8 |
| python asyncio event loop | text | 1636.2 | 43.0 |
| python concurrent.futures | text | 975.4 | 19.8 |
| FastAPI Depends | all | 1343.8 | 19.7 |
| FastAPI settings environment variables | text | 1641.3 | 60.9 |
| django class based views | text | 1828.8 | 66.8 |
| HTTP 500 internal server error | text | 1798.4 | 40.7 |

Counts matched for every term (the script asserts it). Whole cold searches (all stages) on the same copy:
1.07–1.97 s with the seq-scan plan, 61–275 ms after the change.

## Analysis
The GIN plan is 17–68 times faster and grows with posting-list size, not corpus bytes. Limits: PostgreSQL 16
in the container, not the user's 18; duplicated documents make vectors no larger than real ones, so the
real detoast cost at 100k is if anything higher (the user's plan showed 1130 ms for one term). On the
126k copy PostgreSQL 16 did not always choose the seq scan by itself, so the baseline forces it.

## Outcome
Adopt (commit 3453f76). The user should re-run the 100k evaluation to confirm the end-to-end latencies.
