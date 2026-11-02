---
id: EXP-0005
title: Measure search latency and ingestion interference before scaling
status: planned
outcome: inconclusive
date: '2026-11-02'
area: infra
feature: performance-and-scaling
informs:
- ADR-0038
code:
- backend/src/backend/search/service.py
- crawler/src/indexer/worker/runner.py
---

# EXP-0005: Measure search latency and ingestion interference before scaling

## Question

Which stage dominates p95 search latency and index lag under concurrent crawling/indexing on a declared machine?

## Why it matters

This determines whether SQL work, corpus refresh, locks, I/O, or frontend/server overhead should be optimized first.

## Setup

- Hardware / OS / versions: record CPU, RAM, storage, network RTT, PostgreSQL config and runtime versions.
- Data: fixed corpus snapshots at increasing sizes, with realistic common/rare/no-match queries.
- Configuration: one machine/process baseline first; record workers, pool sizes, candidate caps and cache state.
- Safety: use a disposable local corpus/database; do not load-test upstream websites.

## Method

- Baseline: current live FTS path, workers stopped.
- Variables: ingestion enabled, concurrency, corpus size, then one optimization at a time.
- Metrics: p50/p95/p99 latency, error/timeout rate, completed requests/s, SQL statements/rows/buffers, CPU/RSS, pool waits, index lag and useful crawl outcomes.
- Runs: at least repeated warm/cold trials after a documented warm-up; retain raw outputs.

## Reproduce

Start with the existing local services on a disposable database:

```bash
# From backend/, with a disposable DATABASE_URL already configured:
poetry run uvicorn backend.main:app --host 127.0.0.1 --port 8000
# Smoke check from another terminal (not a load benchmark):
curl --get --data-urlencode "q=FastAPI async Python" http://127.0.0.1:8000/search
```

A bounded workload harness and EXPLAIN (ANALYZE, BUFFERS) capture are prerequisites still to implement. Specify duration/concurrency before execution; do not publish guessed QPS from this smoke check.

## Results

Not run. No production capacity or million-requests-per-second result is established.

## Analysis

EXPLAIN ANALYZE executes the statement. Use disposable representative data and separate idle/cold/warm observations. Compare useful outcomes and errors, not only request submission rate.

## Outcome

Inconclusive. Use the resulting bottleneck profile to choose one item from optimization-plan.md.
