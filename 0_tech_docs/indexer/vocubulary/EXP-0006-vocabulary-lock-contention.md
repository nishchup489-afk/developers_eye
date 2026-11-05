---
id: EXP-0006
title: Measure global vocabulary mutex cost after correctness repair
status: done
outcome: reject
date: '2026-11-02'
area: indexer
feature: vocubulary
informs:
- ADR-0036
- ADR-0038
code:
- crawler/src/indexer/vocabulary.py
- crawler/src/indexer/writer.py
---

# EXP-0006: Measure global vocabulary mutex cost after correctness repair

## Question

After INC-0007 is fixed, does the global advisory mutex materially limit useful indexing throughput?

## Why it matters

Removing a lock before proving correctness and contention risks replacing a simple repair model with silent count drift.

## Setup

- Hardware / OS / versions: to be recorded with the run.
- Data: shared/common terms and disjoint terms, inserts, changes, removals and a rebuild.
- Configuration: same document set at 1, 2, 4 and 8 independent writers; record pool limits.
- Prerequisite: repaired increment loop and all paths following mutex-before-document lock order.

## Method

- Baseline: global mutex with correct deltas.
- Variable: writer count first; compare a finer-lock prototype only if contention is demonstrated.
- Metrics: committed documents/s, p95 transaction time, advisory-lock wait, deadlock rate, rebuild duration and exact recount drift.
- Runs: repeated workloads with a full post-run vector-derived reconciliation.

## Reproduce

Existing regression suites, from crawler/:

```bash
poetry run pytest tests/indexer/test_vocabulary.py tests/indexer/test_service_writer.py tests/crawler/worker/test_postgres_pipeline.py -v -rs
```

Set TEST_DATABASE_URL to a disposable PostgreSQL database. No contention benchmark exists yet; add a bounded harness and raw-result capture after fixing INC-0007. Never run a recount concurrently with uncontrolled production writers for this experiment.

## Results

Measured in [EXP-0008](../../infra/performance-and-scaling/EXP-0008-crawl-index-search-at-2m.md): 56 to 66 documents/s at 1, 2, 4 and 8 writers, with exact counts. The lock capped throughput regardless of concurrency.

## Analysis

A performance variant fails if counts diverge even when its throughput rises. A lock can serialize work without being the largest end-to-end cost.

## Outcome

Rejected the global lock. ADR-0043 replaces it with an outbox.
