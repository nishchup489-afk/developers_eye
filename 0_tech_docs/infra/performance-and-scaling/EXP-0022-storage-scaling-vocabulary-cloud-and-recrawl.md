---
id: EXP-0022
title: Corpus scaling, search_vector index choice, vocabulary refresh, Oracle ARM estimate and recrawl yield
status: done
outcome: adopt
date: 2026-11-12
area: infra
feature: performance-and-scaling
informs: [ADR-0042]
---

# EXP-0022: Storage, vocabulary, cloud and recrawl trade-offs

## Question
GIN with fastupdate and the vocabulary outbox are the right storage choices; search_index grows linearly
and fits the Oracle Always Free disk at 2M documents; the configured recrawl intervals are not wasteful.

## Why it matters
Trade-offs 11-15 of [CORE_TRADEOFFS.md](../../../CORE_TRADEOFFS.md): the 2M-document Oracle plan.

## Setup
- Same machine, copy and background load as EXP-0019.
- Scaling: `search_index` sampled to 10K and 50K rows (by `md5(document_id)`) in schemas `c10000`, `c50000`
  with the same indexes; search runs through `search_path`; the full table for 100K.
- Index alternatives: a copy of `search_index` with one `search_vector` index variant at a time.
- Recrawl: the real crawl history in the copy (1,354 pages fetched exactly twice).
- Cloud: no VM existed; `cloud_estimate.py` scales measured CPU by an assumed 0.45 per-core ratio.

## Method
- Scaling: 12 queries x 3 rounds, cold and warm, through `search_documents()`; relation sizes.
- Indexes: none, GIN (fastupdate on), GIN (fastupdate off), GiST; build time, size, match-query latency,
  2,000-row insert cost.
- Vocabulary: 2,000 documents with the outbox, direct per-document upserts (concurrency 4), full rebuild.
- Recrawl: share of pages whose `document.updated_at` moved at the second fetch; one fitted Poisson rate.

## Reproduce
```
crawler\.venv\Scripts\python.exe scripts\tradeoffs\storage_bench.py scaling --rounds 3
crawler\.venv\Scripts\python.exe scripts\tradeoffs\storage_bench.py indexes
crawler\.venv\Scripts\python.exe scripts\tradeoffs\indexer_bench.py vocabulary --docs 2000
crawler\.venv\Scripts\python.exe scripts\tradeoffs\cloud_estimate.py
crawler\.venv\Scripts\python.exe scripts\tradeoffs\crawl_bench.py recrawl
```
Raw: `backend/reports/tradeoffs/11-*.json` to `15-*.json`.

## Results
- Scaling: 127 / 569 / 1,125 MB of search_index at 10K / 50K / ~97K rows (11.6 MB per 1,000); cold p95
  164 / 314 / 667 ms; linear estimate ~22.7 GB at 2M.
- Indexes: GIN 249 MB, match p50 0.79 ms, insert 1.18 ms/row; fastupdate off 2.06 ms/row; GiST 28 MB but the
  planner used a sequential scan (p50 281 ms); no index 785 ms.
- Vocabulary: outbox 61 `search_terms` writes per document and no lock waits; direct upserts 215 per document
  with on average 2 of 4 writers waiting on locks; full rebuild 138 s, 1.94M row writes, 990 MB WAL.
- Cloud (estimate): ~4 searches/s CPU-bound, ~110 docs/s indexing, $0/month Always Free vs $55.48 pay-as-you-go
  and $12.85 local electricity.
- Recrawl: 212 of 1,354 pages (15.7%) changed after 72.7 h; one change per ~17.8 days; 160 KB per fetch.

## Analysis
Supported. Storage is linear and inside the free 200 GB volume (~48 GB database at 2M), but the GIN indexes
(~8 GB) and common-word ranking make RAM and CPU the 2M risks, not disk. Latency was not extrapolated because
the 20K candidate pool cap bends the curve. The recrawl sample is mostly blog pages from RSS sources, so docs
sites probably change less. Limits: one machine with background load; AI grades are not involved here.

## Outcome
Adopt: keep GIN with fastupdate on, keep the vocabulary outbox (rebuild only for repair), keep 30-day docs
recrawl. Follow-ups: conditional GET (ETag / Last-Modified) before shortening any interval; measure search
latency and capacity on the Oracle VM at 1M+ documents.
