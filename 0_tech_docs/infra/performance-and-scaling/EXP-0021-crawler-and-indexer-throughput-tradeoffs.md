---
id: EXP-0021
title: Crawler workers, indexer batch and concurrency, mixed load and connection pools on one machine
status: done
outcome: adopt
date: 2026-11-12
area: infra
feature: performance-and-scaling
informs: [ADR-0042, ADR-0043]
---

# EXP-0021: Crawler and indexer throughput trade-offs

## Question
The deployed worker settings (crawler concurrency 40, indexer batch 200 x concurrency 4, API pool 8 + 2,
crawler pool 2 + 2 per process when running many) sit at or past the knee of their throughput curves, keep
crawler politeness, and fit `max_connections = 100`.

## Why it matters
Trade-offs 6-10 of [CORE_TRADEOFFS.md](../../../CORE_TRADEOFFS.md): they size the Oracle deployment.

## Setup
- Same machine, copy and background load as EXP-0019.
- Crawler: the real worker pipeline in-process against `scripts/tradeoffs/mock_hosts.py`, 64 fake hosts on
  127.0.0.1:80 (40-250 ms pages, 429 under 1 s per host, 503 over 24 in flight). DNS for `*.bench` and the
  public-IP check are relaxed in the benchmark process only. No real site was contacted.
- Indexer: 3,000 sampled documents with their `search_index` rows deleted, rebuilt by the real indexer code.

## Method
- Crawler workers 2, 8, 16, 32, 64; 45 s each after a robots warm-up; pool 4 + 2.
- Indexer batch 25-500 (concurrency 4); concurrency 1-8 (batch 200); 1, 2, 4 shard processes.
- Mixed: 10 search users and a 16-worker crawl, 30 s alone each and 30 s together.
- Pool: 25 concurrent searches for 20 s per pool size 1+0, 2+2, 4+2, 8+2, 16+4; checkout wait timed in the pool.
- Lock waits sampled from `pg_stat_activity` every 50 ms; WAL from `pg_wal_lsn_diff`.

## Reproduce
```
crawler\.venv\Scripts\python.exe scripts\tradeoffs\crawl_bench.py workers --workers 2 8 16 32 64 --seconds 45
crawler\.venv\Scripts\python.exe scripts\tradeoffs\indexer_bench.py batch --docs 3000
crawler\.venv\Scripts\python.exe scripts\tradeoffs\indexer_bench.py concurrency --docs 3000
crawler\.venv\Scripts\python.exe scripts\tradeoffs\indexer_bench.py processes --docs 3000
crawler\.venv\Scripts\python.exe scripts\tradeoffs\crawl_bench.py mixed --workers 16 --users 10 --seconds 30
crawler\.venv\Scripts\python.exe scripts\tradeoffs\crawl_bench.py pool --tasks 25 --seconds 20
```
Raw: `backend/reports/tradeoffs/06-*.json` to `10-*.json`.

## Results
- Crawler: 5.1 / 14.0 / 14.8 / 13.8 / 12.2 pages/s at 2 / 8 / 16 / 32 / 64 workers; zero 429 or 503,
  smallest same-host gap 2.4 s; ~0.65 core Python, ~0.2 core PostgreSQL.
- Indexer batch: 50.4 / 52.5 / 73.2 / 46.6 / 79.4 docs/s at 25 / 50 / 100 / 250 / 500; `search_terms` row
  writes per document 125 / 97 / 79 / 59 / 48; per-document p50 ~21 ms throughout; no lock waits.
- Indexer concurrency: 56.6 / 74.1 / 72.5 / 81.2 docs/s at 1 / 2 / 4 / 8; processes 38.0 / 144.8 / 208.8
  docs/s at 1 / 2 / 4.
- Mixed: search 12.2 vs 13.3 successful/s, p95 3.95 vs 2.97 s (within noise); crawl 13.7 to 8.3 pages/s (-39%).
- Pool: 3.8 / 12.9 / 14.3 / 19.2 / 19.6 searches/s; checkout wait p95 5.0 / 2.4 / 2.0 / 1.7 / 1.0 s; only 1+0 errored.

## Analysis
Mostly supported. Politeness held everywhere. The crawler knee is 8-16 workers per ~64 hosts, well below 40,
but real hosts are slower and more numerous, so 40 is not harmful (it only queues jobs on politeness).
The indexer is bound by one Python event loop per process, so shards, not in-process concurrency, add
throughput. Search competes with crawling for PostgreSQL CPU, not the other way round. Pool throughput stops
growing at 10 connections. Limits: Windows, background crawler and other programs; first runs of the crawler
and indexer-process benchmarks were invalid (leftover leases; children re-sampled documents) and were rerun
after fixes.

## Outcome
Adopt: crawler 16+ workers per process scaled by hosts; indexer batch 100-200 and concurrency 2-4 with more
shards for throughput; API pool 8 + 2; crawler 2 + 2 per process with 20 processes (96 of 100 connections).
