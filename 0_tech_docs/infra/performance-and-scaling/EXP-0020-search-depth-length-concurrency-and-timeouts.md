---
id: EXP-0020
title: Search candidate depth, query length, concurrency and timeout budget on the 100K corpus
status: done
outcome: adopt
date: 2026-11-12
area: infra
feature: performance-and-scaling
informs: [ADR-0046]
---

# EXP-0020: Search depth, query length, concurrency and timeouts

## Question
The live search settings (100 candidates per channel, one uvicorn worker with a 16-slot cap, 3 s / 4 s
deadlines) are the right trade-off on the 100K corpus: deeper pools do not improve relevance, and the
cap and deadline turn overload into fast rejections rather than timeouts.

## Why it matters
Trade-offs 2-5 of [CORE_TRADEOFFS.md](../../../CORE_TRADEOFFS.md); they set public search limits (ADR-0046).

## Setup
- Same machine, copy and background load as EXP-0019 (crawler writing to the real database).
- Labels for depth: the AI-reviewed checklist-25 grades (EXP-0014).
- HTTP tests: uvicorn, 1 worker, DB_POOL_SIZE=8, DB_MAX_OVERFLOW=2, rate limit lifted, 77 real and
  common-word queries, closed-loop users without think time.

## Method
- Depth: per-channel LIMIT 50/100/200/500 on the live retrieval SQL, BM25 ranking, warm DF; 25 x 3 rounds.
- Length: 8 queries each of 1, 2, 5, 10 words through `search_documents()`; 5 cold + 5 warm rounds; EXPLAIN ANALYZE.
- Concurrency: 1, 10, 25, 50, 100 users, 20 s each, run twice.
- Timeouts: fresh server per statement deadline 1, 2, 5 s; 25 users, 30 s; run twice.

## Reproduce
```
crawler\.venv\Scripts\python.exe scripts\tradeoffs\search_bench.py depth --rounds 3
crawler\.venv\Scripts\python.exe scripts\tradeoffs\search_bench.py complexity --rounds 5
crawler\.venv\Scripts\python.exe scripts\tradeoffs\http_bench.py concurrency --seconds 20
crawler\.venv\Scripts\python.exe scripts\tradeoffs\http_bench.py timeout --users 25 --seconds 30
```
Raw: `backend/reports/tradeoffs/02-*.json` to `05-*.json`.

## Results
- Depth: judged Recall@100 0.878 / **0.935** / 0.897 / 0.887 and nDCG@10 0.681 / **0.693** / 0.671 / 0.667
  for 50 / 100 / 200 / 500; warm p95 518 / 426 / 433 / 562 ms.
- Length: cold p95 673 / 607 / 465 / 408 ms and warm p50 155 / 100 / 88 / 24 ms for 1 / 2 / 5 / 10 words;
  every length uses Bitmap Index Scan on the GIN index; one common word matches about 12K documents.
- Concurrency: about 25 successful searches/s at 10-25 users; above that, 503s from the cap and p95 of
  3-9 s. At saturation PostgreSQL used about 7 cores and the API 0.6: roughly 0.27 s of database CPU per search.
- Timeouts: 1 / 0 / 0 timeouts (504) out of about 1,900 requests at 1 / 2 / 5 s; completed 789 / 786 / 673.

Full tables: CORE_TRADEOFFS.md items 2-5.

## Analysis
Supported. Depth 100 has the best recall and nDCG; deeper pools add long, loosely matching pages that BM25
promotes. Short common-word queries, not long ones, are the expensive path, and PostgreSQL CPU is the
throughput limit. The deadline rarely fires at 100K documents because the 16-slot cap rejects excess load
first. Limits: one Windows machine with other heavy programs running; the two runs of item 4 differ by up
to 3x at low load, so treat latency as an upper bound.

## Outcome
Adopt the current settings (depth 100, cap 16, 3 s / 4 s; 2 s / 3 s would also do). Follow-up: make
one- and two-word queries cheaper (warm DF for the top vocabulary at startup, smaller candidate pool for
one-word queries) and remeasure at 2M documents.
