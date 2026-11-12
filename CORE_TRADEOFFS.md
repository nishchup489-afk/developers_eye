# Core trade-offs: measured results

Fifteen engineering trade-offs for Developer's Eye, each measured on the real
local corpus. How every number was calculated, step by step:
[guide/tradeoffs_calculation.md](guide/tradeoffs_calculation.md). Raw reports:
[backend/reports/tradeoffs/](backend/reports/tradeoffs/). Scripts:
[scripts/tradeoffs/](scripts/tradeoffs/). Tech-doc records:
EXP-0019 (item 1), EXP-0020 (items 2-5), EXP-0021 (items 6-10), EXP-0022 (items 11-15).

## Read this first

- **Data.** A `pg_dump` copy (`developers_eye_bench`) of the real database taken
  2026-11-12: 100,141 indexed documents (101,042 document rows), 968K vocabulary
  terms, 2.4 GB. The copy was used so nothing touched the real database.
- **Machine.** Intel Core Ultra 7 265F (20 cores), 32 GB RAM, NVMe SSD, Windows 11,
  PostgreSQL 18.3 with **default settings** (shared_buffers 128 MB, work_mem 4 MB),
  Python 3.14.4. Production (`deploy/postgresql.conf`) uses 6 GB shared buffers, so
  the server will cache far more than this machine did.
- **Background load.** Your crawler was crawling into the real database on the
  same PostgreSQL server during every run, and the machine sat at 30-31 of 32 GB
  RAM used and 4-14 busy cores from other programs. Latency numbers are therefore
  pessimistic and vary between runs; where a run was repeated both results are shown.
- **Relevance labels.** The human judging page has **0 grades** so far. Relevance
  uses the 25-query, 328-grade **AI-reviewed** set (EXP-0014). Treat P@10/MRR/nDCG
  as a provisional signal until people grade.
- **Estimates are labelled.** Item 14 (no Oracle VM exists yet), the 2M-document
  column of item 11 and the interval model of item 15 are calculations from local
  measurements, not measurements.

## Summary

| # | Trade-off | Result | Recommendation |
| --- | --- | --- | --- |
| 1 | Custom BM25 vs PostgreSQL ts_rank | nDCG tie (0.693 vs 0.689); PG better P@10 (0.780 vs 0.708) and MRR; BM25 +130 ms cold p50 | Keep for now; get human grades, then likely rank with ts_rank_cd |
| 2 | Candidate depth 50/100/200/500 | 100 has best recall@100 (0.935) and nDCG (0.693); deeper is slower and worse | Keep 100 |
| 3 | Query length 1/2/5/10 terms | 1-2 word queries are the slow ones (p95 ~0.6-0.7 s); all use GIN | Make common-word queries cheaper |
| 4 | Search concurrency 1-100 users | ~25 successful searches/s cap; PostgreSQL ~7 cores at saturation; 503s beyond 16 in flight | Keep the 16-slot cap |
| 5 | Timeout budget 1/2/5 s | ~0% timeouts at any budget at 100K docs; the cap rejects first | 2-3 s is enough; revisit at 2M |
| 6 | Crawler workers 2-64 | Plateau ~15 pages/s at 8-16 workers, zero politeness violations | 16 per process; add hosts, not workers |
| 7 | Indexer batch 25-500 | Throughput +50% from 25 to 100+; vocab writes per doc 125 to 48 | 100-200 (deploy 200) |
| 8 | Indexer concurrency / processes | In-process flat after 2 (~75 docs/s); 4 processes 209 docs/s; no lock waits | 2-4 per process, scale with shards |
| 9 | Crawl + search together | Search unaffected; crawl -39% | Fine to share one server |
| 10 | Connection pool | Throughput flat past 10 connections; 1 connection times out | API 8+2, crawler 2+2 per process (96/100 budget) |
| 11 | Corpus 10K/50K/100K | 11.6 MB per 1K docs (linear); cold p95 164 to 667 ms | ~23 GB search_index at 2M; measure latency there |
| 12 | Index alternatives | GIN 0.8 ms vs seq scan 785 ms; GiST unused by planner; fastupdate off doubles insert cost | Keep GIN, fastupdate on |
| 13 | Vocabulary refresh | Outbox: 61 writes/doc, 0 lock waits; direct upsert: 215 writes/doc, half the writers waiting; rebuild: 138 s, 1 GB WAL | Keep the outbox |
| 14 | Local vs Oracle ARM (estimate) | ARM ~0.45x per core; ~4 searches/s CPU-bound; $0 vs $12.85/month | Use Always Free; measure there first |
| 15 | Recrawl frequency | 15.7% of pages changed in 72.7 h; one change per ~18 days | 30 days for docs; add conditional GET before going shorter |

---

## P0: Search engine performance and relevance

### 1. Custom BM25 vs PostgreSQL ts_rank (EXP-0019)

Same candidates (live text + code + title channels, 100 per channel), ranked two
ways; 25 queries x 5 rounds x {cold, warm DF cache}.

| Ranker | P@10 | MRR@10 | nDCG@10 | Top 10 graded | p50 cold | p95 cold | p50 warm | p95 warm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Custom BM25 (live) | 0.708 | 0.900 | **0.693** | 96.8% | 146 ms | 674 ms | 45 ms | 386 ms |
| PostgreSQL ts_rank_cd | **0.780** | **0.927** | 0.689 | 100% | 16 ms | 426 ms | 13 ms | 309 ms |
| Retrieval alone (shared) | | | | | 11 ms | 421 ms | 10 ms | 306 ms |

- nDCG is a tie (0.693 vs 0.689). PostgreSQL wins P@10 by 0.072 and MRR by 0.027.
- BM25 costs **+130 ms at p50 when the DF cache is cold** and +32 ms warm. The p95 is
  dominated by retrieval (306-421 ms), not by either ranker.
- 3.2% of BM25's top 10 were URLs no grader saw (counted as irrelevant), so BM25's
  precision may be slightly understated.
- **Verdict:** on current (AI) labels, custom BM25 does not beat PostgreSQL's ranking
  and costs 3x the median latency. Do not remove it yet: grade the 36 human queries
  on the admin Search quality page and rerun `search_bench.py ranking`. If humans
  agree, rank with `ts_rank_cd` and keep BM25 only as a diagnostic.

### 2. Candidate retrieval depth (EXP-0020)

Candidates per channel (the title channel always adds up to 30), BM25 ranking, warm DF cache.

| Depth | Mean candidates | Judged Recall@100 | Candidate recall | nDCG@10 | P@10 | p50 | p95 | DB CPU / query |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | 44 | 0.878 | 0.878 | 0.681 | 0.680 | 42 ms | 518 ms | 91 ms |
| **100 (live)** | 72 | **0.935** | 0.939 | **0.693** | 0.708 | 53 ms | 426 ms | 82 ms |
| 200 | 115 | 0.897 | 0.939 | 0.671 | 0.676 | 67 ms | 433 ms | 93 ms |
| 500 | 169 | 0.887 | 0.955 | 0.667 | 0.672 | 59 ms | 562 ms | 94 ms |

- Going from 100 to 500 finds 1.6 points more known-relevant documents somewhere in
  the pool, but BM25 then pushes some of them **out** of the top 100 and the top 10
  (nDCG falls 0.693 to 0.667): extra candidates are mostly long pages that BM25 likes.
- Depth 50 loses 5.7 points of recall. "Recall" here is over known graded positives
  only, not true corpus recall.
- Python CPU per query stays 8-12 ms; DB CPU numbers include the background crawler.
- **Verdict:** keep 100. Deeper pools only help if the ranker gets better at rejecting
  long, loosely matching pages.

### 3. Query complexity (EXP-0020)

Full `search_documents()` (retrieval, BM25, metadata, snippets), mode `all`,
8 queries per length x 5 rounds.

| Terms | Mean candidates | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Python CPU / query | Text-match plan (first query) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 212 | 187 ms | 673 ms | 155 ms | 695 ms | 28 ms | Bitmap Index Scan > Bitmap Heap Scan, 12,093 rows, 18.9 ms |
| 2 | 152 | 275 ms | 607 ms | 100 ms | 273 ms | 27 ms | same, 830 rows, 2.4 ms |
| 5 | 62 | 252 ms | 465 ms | 88 ms | 272 ms | 35 ms | same, 77 rows, 1.0 ms |
| 10 | 10 | 148 ms | 408 ms | 24 ms | 155 ms | 32 ms | same, 10 rows, 1.9 ms |

- **Short queries are the expensive ones**, not long ones. One common word matches
  ~12K documents; ranking (ts_rank over up to 20K matches, then DF/TF loads) is the cost,
  the GIN match itself is under 20 ms. Every length uses the GIN index (no seq scans).
- Queries AND their terms, so 10-word queries keep only ~10 candidates (1 of 8 returned nothing).
- Cold DF cache adds 90-250 ms at p50 for 2-10 terms (one GIN DF count per new term).
- **Verdict:** protect the 1-2 word path: keep the DF cache warm (prefetch DF for the
  top vocabulary at startup) and consider a lower candidate pool for one-word queries.

### 4. Search concurrency (EXP-0020)

Real HTTP against one uvicorn worker (as in `deploy/docker-compose.yml`): pool 8 + 2,
in-process cap `SEARCH_MAX_CONCURRENT=16` (beyond it the API answers 503 at once),
3 s statement / 4 s total deadline, rate limit lifted. Closed-loop users with no think
time, 20 s per level, 77 real and common queries. Run twice; run 1 had less background load.

| Users | Requests/s (run 1 / 2) | Successful/s (1 / 2) | Error rate (1 / 2) | p50 (1 / 2) | p95 (1 / 2) | p99 (1 / 2) | API CPU (run 2) | PostgreSQL CPU (run 2) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4.1 / 1.3 | 4.1 / 1.2 | 0% / 3.4% (504) | 85 / 197 ms | 954 / 2,944 ms | 1,176 / 4,031 ms | 0.04 cores | 0.7 cores |
| 10 | 24.9 / 11.2 | 24.9 / 10.7 | 0% / 5.2% (504) | 333 / 320 ms | 1,252 / 4,034 ms | 1,555 / 4,265 ms | 0.26 | 2.6 |
| 25 | 39.9 / 63.9 | 25.2 / 24.6 | 37% / 61% (503) | 562 / 155 ms | 1,680 / 1,515 ms | 2,132 / 2,276 ms | 0.63 | 6.9 |
| 50 | 29.7 / 40.6 | 24.1 / 23.8 | 19% / 41% (503) | 1,142 / 843 ms | 4,132 / 3,268 ms | 6,472 / 4,746 ms | 0.58 | 6.9 |
| 100 | 28.2 / 33.5 | 20.1 / 22.2 | 29% / 34% (503) | 1,955 / 1,787 ms | 9,462 / 8,308 ms | 13,551 / 12,092 ms | 0.56 | 7.0 |

- **Capacity is about 25 successful searches/s** on this machine, reached at 10-25 users;
  beyond that extra users get fast 503s ("busy") and the queue inside uvicorn grows,
  so p95 climbs from ~1.5 s to 8-9 s.
- **PostgreSQL is the bottleneck, not Python**: at saturation the API process used
  0.6 of a core while PostgreSQL used ~7 cores, i.e. **~0.27 s of database CPU per
  successful search** (7 cores x 20 s / 506). Most of it is ranking up to 20K matches
  of common words (items 3 and 11).
- Errors: 503 from the concurrency cap (by design), 504 when the 3 s deadline fired
  under background load, one socket ReadError at 50 users.
- **Verdict:** keep the 16-slot cap; it turns overload into fast 503s instead of
  timeouts. The lever for more throughput is cheaper common-word queries, not more
  API workers.

### 5. Search timeout budget (EXP-0020)

Fresh server per budget (cold DF cache), 25 users for 30 s, statement deadline
1/2/5 s (total = +1 s).

| Statement deadline | Requests | Completed (200) | Timeouts (504) | Timeout rate | Busy (503) | p50 | p95 | p99 | PostgreSQL CPU | API CPU |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 s | 1,865 | 789 | 1 | 0.05% | 1,075 | 211 ms | 1,470 ms | 2,017 ms | 7.0 cores | 0.65 |
| 2 s | 2,059 | 786 | 0 | 0% | 1,273 | 150 ms | 1,390 ms | 2,090 ms | 7.0 | 0.65 |
| 5 s | 1,808 | 673 | 0 | 0% | 1,135 | 141 ms | 1,659 ms | 2,590 ms | 5.9 | 0.56 |

(First run, less background load: 1 s 813 completed / 1 timeout, 2 s 787 / 0, 5 s 774 / 0.)

- Almost no single statement runs past 1 s on this corpus, so the budget barely
  matters at 100K documents: the 16-slot cap rejects excess load first, and completed
  queries are flat (~790) from 1 s to 2 s.
- 5 s completed fewer (673): slow queries hold slots longer, so more requests bounce off the cap.
- Memory did not depend on the budget (PostgreSQL RSS ~2.65 GB in all three).
- **Verdict:** 2 s statement / 3 s total is enough today (the live 3 s / 4 s is safe
  too). Revisit when the corpus grows, because common-word ranking cost grows with it.

---

## P1: Crawler and indexing performance

### 6. Crawler concurrency (EXP-0021)

**Mock hosts, not real sites.** The real crawler (claim, robots, shared per-host
politeness, fetch, parse, process, write) crawled 64 local mock hosts for 45 s per
setting: one process, pool 4 + 2 (as deployed). The mock serves 40-250 ms pages,
returns 429 if a host is hit twice within 1 s and 503 above 24 requests in flight.

| Workers | Docs/s | Pages stored | HTTP 429 | HTTP 503 | Smallest gap to one host | Crawler CPU | PostgreSQL CPU | Crawler RAM | Unfinished at stop |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 5.1 | 229 | 0 | 0 | 11.2 s | 0.24 cores | 0.14 | 208 MB | 1 |
| 8 | 14.0 | 628 | 0 | 0 | 3.9 s | 0.64 | 0.19 | 287 MB | 6 |
| 16 | **14.8** | 667 | 0 | 0 | 3.2 s | 0.65 | 0.20 | 322 MB | 5 |
| 32 | 13.8 | 619 | 0 | 0 | 3.3 s | 0.64 | 0.18 | 256 MB | 25 |
| 64 | 12.2 | 550 | 0 | 0 | 2.4 s | 0.63 | 0.17 | 300 MB | 45 |

(A first run of this benchmark was invalid: leases left by a cancelled run blocked hosts
for the next one. The script now releases them; numbers above are the fixed rerun.)

- **Politeness held at every setting:** zero 429s, and no host was ever asked twice
  within 2 s (smallest gap 2.4 s at 64 workers).
- Throughput **plateaus at 8-16 workers (~14-15 pages/s)**, below the politeness ceiling
  of 64 hosts / 2 s = 32 pages/s. Each host gets a page about every 4.5 s: the crawler's
  own per-host cycle (claim, politeness reservation, fetch, write) adds ~2.5 s to the 2 s gap.
- More than 16 workers only adds jobs that wait on politeness: throughput falls slightly,
  and more work is in flight when the process stops.
- CPU stays at ~0.65 core of Python and ~0.2 core of PostgreSQL; RAM 200-320 MB.
- **Verdict:** 16 workers per process for ~64 active hosts; scale with more hosts
  (sources), not more workers. On real sites per-host gaps are longer (robots crawl-delay,
  slower servers), so the deploy setting of 40 is reasonable for hundreds of hosts.

### 7. Indexer batch size (EXP-0021)

3,000 sampled documents re-indexed per run (index rows deleted first, so it is the
new-document path), concurrency 4, vocabulary outbox drained after every batch.

| Batch | Docs/s | Per-doc transaction p50 | p95 | Batch latency p50 | p95 | Drain p95 | search_terms row writes / doc | Peak RSS | Lock waits |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 25 | 50.4 | 20 ms | 110 ms | 0.37 s | 1.2 s | 0.37 s | 125 | 114 MB | 0 |
| 50 | 52.5 | 22 ms | 220 ms | 0.71 s | 2.5 s | 0.64 s | 97 | 116 MB | 0 |
| 100 | 73.2 | 21 ms | 85 ms | 1.2 s | 2.9 s | 0.71 s | 79 | 117 MB | 0 |
| 250 | 46.6 | 22 ms | 139 ms | 3.5 s | 9.1 s | 3.7 s | 59 | 118 MB | 0 |
| 500 | 79.4 | 21 ms | 140 ms | 5.9 s | 8.6 s | 2.8 s | 48 | 117 MB | 0 |

- Per-document work is flat (~21 ms p50); bigger batches mainly cut **vocabulary write
  amplification** (125 to 48 `search_terms` row writes per document, because the drain
  sums deltas per term) and per-batch overhead.
- Throughput is noisy (the 250 run dipped while the live crawler was busy); the trend
  is +50% from 25 to 100-500. Memory does not grow with batch size.
- Cost of big batches: a batch's results become visible later (p95 batch 8-9 s at 250-500).
- **Verdict:** 100-200 (deploy uses 200). Above that, gains are within noise and
  freshness gets worse.

### 8. Indexer concurrency (EXP-0021)

Same 3,000 documents, batch 200, pool sized to concurrency + 1 (+2 overflow).

| In-process concurrency | Docs/s | Per-doc p50 | Per-doc p95 | Lock waits (mean / max sessions) | DB CPU (cores) | Python CPU (cores) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 56.6 | 7.6 ms | 18.6 ms | 0 / 0 | 0.52 | 0.37 |
| 2 | 74.1 | 10.7 ms | 26.9 ms | 0 / 0 | 0.59 | 0.45 |
| 4 (deploy) | 72.5 | 21.7 ms | 157 ms | 0 / 0 | 0.61 | 0.45 |
| 8 | 81.2 | 39.8 ms | 319 ms | 0 / 0 | 0.62 | 0.43 |

Separate **processes** (each concurrency 4, batch 200, splitting the same 3,000
documents by `id % processes`, like `INDEXER_SHARD_COUNT`):

| Processes | Docs/s | Lock waits | PostgreSQL CPU | Peak Python RAM (all) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 38.0 | 0 | 0.45 cores | 201 MB |
| 2 | 144.8 | 0 | 1.26 | 306 MB |
| 4 | **208.8** | 0 | 1.63 | 486 MB |

(The 1-process run was slower than the in-process runs above because of background
load at that moment; 2 and 4 processes are the reliable signal. A first run of this
benchmark was invalid: the child processes re-sampled different documents. Fixed and rerun.)

- No session ever waited on a lock: `FOR UPDATE` is per document and the vocabulary
  outbox removed the shared hot rows (compare item 13).
- One process saturates at ~75-80 docs/s with about half a core of Python: the event
  loop, not PostgreSQL, is the limit. More in-process concurrency only stretches
  per-document latency, while **more processes scale almost linearly** (4 processes:
  209 docs/s, 1.6 cores of PostgreSQL).
- **Verdict:** concurrency 2-4 per process, and add shards (`INDEXER_SHARD_COUNT`)
  for throughput. At 4 shards, 2M documents index in about 2.7 hours locally.

### 9. Crawl + search simultaneously vs separately (EXP-0021)

Three 30 s phases on the same API server and mock hosts: 10 search users alone,
a 16-worker crawl alone, then both together.

| Phase | Searches/s | Search p50 | Search p95 | Search 504s | Crawl pages/s | PostgreSQL CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Search only | 12.2 | 210 ms | 3,952 ms | 17 | | 3.0 cores |
| Crawl only | | | | | 13.7 | 0.2 cores |
| Both | 13.3 | 255 ms | 2,973 ms | 16 | **8.3 (-39%)** | 3.4 cores |

- Crawling did **not** measurably slow search: search throughput and p95 were the
  same within this machine's noise (the p95 even came out lower in the mixed phase).
- Search **did** slow crawling by 39%: both compete for PostgreSQL, and search takes
  ~3 cores of it (item 4), while a crawl needs only ~0.2.
- **Verdict:** running both on one server is fine for search users. Expect crawl
  throughput to drop when search traffic is high; if crawl speed matters, crawl at night
  or cap search concurrency lower, not the other way round.

### 10. Database connection pool size (EXP-0021)

25 concurrent in-process searches for 20 s per pool size (one session each, warm
DF cache, mixed query set, 3 s statement timeout, 5 s pool timeout).

| pool + overflow | Max connections | Searches/s | p50 | p95 | Checkout wait p50 | p95 | max | Errors | Peak PG RSS (sum) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 1 + 0 | 1 | 3.8 | 4.3 s | 5.4 s | 4.4 s | 5.0 s | 5.0 s | 39 pool timeouts | 1.1 GB |
| 2 + 2 | 4 | 12.9 | 1.8 s | 3.1 s | 1.5 s | 2.4 s | 3.6 s | 0 | 1.6 GB |
| 4 + 2 | 6 | 14.3 | 1.6 s | 2.9 s | 1.2 s | 2.0 s | 4.1 s | 0 | 2.0 GB |
| 8 + 2 (API in deploy) | 10 | 19.2 | 1.1 s | 2.9 s | 0.8 s | 1.7 s | 3.0 s | 0 | 2.6 GB |
| 16 + 4 | 20 | 19.6 | 1.1 s | 3.0 s | 0.10 s | 1.0 s | 1.6 s | 0 | 4.1 GB |

- Throughput stops growing at 10 connections for one process: past that, more
  connections only move the wait from the pool into PostgreSQL/CPU.
- Each extra connection costs PostgreSQL memory (sum of backend RSS, an upper bound:
  shared memory counts once per backend).
- Connection budget with `max_connections = 100`: 20 crawler processes x (2 + 2) = 80,
  API 8 + 2 = 10, one indexer 4 + 2 = 6, total 96. That leaves 4 for psql, backups and
  the admin console, so do not raise any pool without lowering another.
- **Verdict:** API 8 + 2 (as deployed); crawler 2 + 2 per process when running many processes.

---

## P2: Storage, scalability and infrastructure

### 11. Corpus scaling (EXP-0022)

`search_index` sampled to each size (same indexes), full search path,
12 queries x 3 rounds x {cold, warm}.

| Documents | search_index total | Heap | TOAST (vectors) | GIN text | GIN code | Mean matches / query | Cold p50 | Cold p95 | Warm p50 | Warm p95 | Peak PG RSS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10,000 | 127 MB | 9 MB | 63 MB | 39 MB | 16 MB | 178 | 45 ms | 164 ms | 37 ms | 181 ms | 1.22 GB |
| 50,000 | 569 MB | 43 MB | 313 MB | 145 MB | 67 MB | 884 | 82 ms | 314 ms | 52 ms | 236 ms | 1.28 GB |
| 96,941* | 1,125 MB | 86 MB | 649 MB | 261 MB | 126 MB | 1,698 | 233 ms | 667 ms | 67 ms | 537 ms | 1.28 GB |
| **2,000,000 (linear estimate)** | **~22.7 GB** | | | **~5.2 GB** | **~2.5 GB** | ~34,000 | not extrapolated | | | | |

\* the live table holds 100,141 rows but `count(*)` saw 96,941 visible at test time
because the first (broken) indexer-process run had deleted a 3,000-row sample and not rebuilt it; sizes are per row, so this does not change the per-document numbers.

- Storage is linear: **11.6 MB per 1,000 documents**, 58% of it the TOASTed vectors.
  The whole database (documents, frontier, vocabulary) was 2.4 GB at 100K, so about
  24 KB per document; 2M documents is roughly 48 GB of disk, inside the 200 GB free block volume.
- Latency grows faster than size between 50K and 100K (p95 314 to 667 ms) because
  common words match more documents and every match must be ranked up to the 20K pool cap.
  Beyond ~1M documents the cap holds the match work roughly constant, so a straight-line
  extrapolation to 2M would be wrong in either direction; it has to be measured.
- RAM: the GIN indexes are 387 MB at 100K and ~8 GB at 2M, more than this machine's
  128 MB shared_buffers but inside production's 6 GB shared buffers + 16 GB OS cache.

### 12. PostgreSQL index alternatives for search_vector (EXP-0022)

A copy of `search_index` (100,141 rows) with one index variant at a time; the
retrieval match query (`@@ websearch_to_tsquery`, LIMIT 20000), 12 queries x 3 rounds;
2,000 rows re-inserted with the index in place.

| Variant | Build | Size | Match p50 | Match p95 | Plan | Insert cost / row |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| None | 0 | 0 | 785 ms | 987 ms | Seq Scan | 0.11 ms |
| **GIN, fastupdate on (current)** | 14.1 s | 249 MB | **0.79 ms** | **6.2 ms** | Bitmap Heap Scan | 1.18 ms |
| GIN, fastupdate off | 13.8 s | 249 MB | 0.81 ms | 6.6 ms | Bitmap Heap Scan | 2.06 ms |
| GiST | 5.3 s | 28 MB | 281 ms | 734 ms | Seq Scan (planner rejected GiST) | 0.21 ms |

- GIN is 1,000x faster than a scan for a 0.25 GB price. `fastupdate` keeps inserts
  43% cheaper at no query cost here (its pending list is flushed by autovacuum).
- GiST is 9x smaller but lossy for tsvector: PostgreSQL chose a sequential scan over
  it for every query, so it buys nothing.
- **Verdict:** keep GIN with fastupdate on.

### 13. Vocabulary/statistics refresh strategy (EXP-0022)

2,000 sampled documents, concurrency 4.

| Strategy | What it does | search_terms row writes / doc | WAL | Lock waits (mean / max sessions) | Freshness |
| --- | --- | ---: | ---: | --- | --- |
| **Outbox + batched drain (current)** | one `vocabulary_change` row per doc, summed per term per batch | **61** | 155 KB/doc incl. indexing | **0 / 0** | after the batch's drain: p95 1.1 s |
| Direct upsert per document | `INSERT ... ON CONFLICT +1` for every term of every doc | 215 | 63 KB/doc (vocabulary only) | **2.0 / 3** of 4 writers | immediate |
| Full rebuild | recount 100K docs, replace 968K terms | 1.94M rows per rebuild | 990 MB per rebuild | 0 (writers must be stopped) | as old as the last rebuild (138 s to run) |

- Direct upserts write 3.5x more rows and, with only 4 writers, half the writers were
  waiting on a common term's row lock at any moment; with more indexers this gets worse
  (the original EXP-0006 problem).
- A full rebuild is the right repair tool for drift, not a refresh strategy: 138 s and
  ~1 GB of WAL every time, growing with the corpus.
- **Verdict:** keep the outbox; run a rebuild only after bulk deletes or a known drift.

### 14. Local machine vs Oracle Always Free ARM VM (EXP-0022, ESTIMATE)

**No Oracle VM exists yet, so this is an estimate**, computed by `cloud_estimate.py`
from the local reports. Assumptions (all command-line parameters): one Ampere A1 core
does **0.45x** the work of one core here (range 0.35-0.55), 4 OCPU at 70% target
utilisation, PostgreSQL idle CPU (0.12 cores) subtracted.

| | Local (measured) | Oracle A1 4 OCPU / 24 GB (estimate) |
| --- | --- | --- |
| CPU per search (API + PostgreSQL) | 307 ms | 683 ms |
| Search throughput | 24.6/s (best level, item 4) | **~4 searches/s** CPU-bound |
| Single-user search p50 / p95 | 197 / 2,944 ms (run 2), 85 / 954 ms (run 1) | 85-440 ms / 1.0-6.5 s |
| CPU per crawled page | 49 ms | 110 ms |
| Crawl throughput | 14.8 pages/s | ~25 pages/s of CPU headroom; politeness (hosts / 2 s) binds first |
| CPU per indexed document | 11 ms | 25 ms |
| Indexing throughput | 79 docs/s (1 process), 209 (4 processes) | ~110 docs/s; 2M documents in ~5 h |
| search_index at 2M | | ~22.7 GB: more than the RAM left after 6 GB shared buffers, so cold reads hit disk |
| **Monthly cost** | **$12.85** electricity (110 W, $0.16/kWh; excludes hardware and internet) | **$0** inside Always Free; $55.48 at pay-as-you-go list price for the same shape |

- The search CPU figure is inflated by the background load (it includes other PostgreSQL
  work during the test), so ~4 searches/s on ARM is a floor, not a forecast. It still says
  the same thing as items 3, 4 and 11: **common-word ranking cost decides capacity**,
  and on 4 ARM cores it matters ~5x more than on this 20-core PC.
- Memory, not CPU, is the 2M-document risk: the GIN indexes alone are ~8 GB at 2M.
- **Verdict:** Always Free is the right home (cost $0), but measure on the VM before
  launch: run `http_bench.py concurrency` there, replace `--arm-per-core` with the measured
  ratio, and fix the common-word path first.

### 15. Recrawl frequency (EXP-0022)

Measured from your real crawl history: **1,354 pages fetched twice, 72.7 h apart
on average; 212 (15.7%) had changed content** (`document.updated_at` moved at the
second fetch). Mean fetch was 160 KB. The crawler has no conditional GET
(no ETag / If-Modified-Since), so every recrawl downloads the full page.

Fitted change rate (one shared Poisson rate): 0.056 changes per page per day, a
change every **17.8 days** on average. **Model** for other intervals (labelled estimate):

| Recrawl every | Fetches / month per 100K docs | Download / month, 100K | Download / month, 2M | Changed-page yield | Useful fetches / month per 100K | Mean stale share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 day | 3,000,000 | 481 GB | 9.6 TB | 5.5% | 163,888 | 2.8% |
| 3 days | 1,000,000 | 160 GB | 3.2 TB | 15.5% | 155,098 | 8.0% |
| 7 days | 428,571 | 69 GB | 1.4 TB | 32.5% | 139,345 | 17.3% |
| 14 days | 214,286 | 34 GB | 687 GB | 54.5% | 116,692 | 30.8% |
| 30 days (most website sources now) | 100,000 | 16 GB | 320 GB | 81.5% | 81,462 | 51.7% |
| 60 days | 50,000 | 8 GB | 160 GB | 96.6% | 48,282 | 71.4% |

- The measured pages are mostly blog posts reached through RSS sources; reference
  docs probably change more slowly, so the model overstates churn for docs sites.
- Going from 30 to 7 days quadruples bandwidth to cut the stale share from 52% to 17%.
- Ingress is free on Oracle; the binding cost is politeness time, not money:
  at 2 s per host, 2M pages every 7 days needs ≥ 6.6 pages/s sustained across hosts.
- **Verdict:** keep 30 days for docs, 1-3 days for feed entry points only (as now), and
  add conditional GET (ETag/Last-Modified) before shortening any interval: it would make
  an unchanged recrawl cost a few hundred bytes instead of 160 KB.

---

## What was not measured, and why

- **Human relevance.** No human grades exist yet (0 of 467 pooled rows), so items 1-2
  use AI grades. Grade on the admin Search quality page, then rerun `search_bench.py ranking` and `depth`.
- **Oracle VM.** Item 14 is an estimate; nothing ran on ARM.
- **2M documents.** Item 11 measured up to 100K; storage is extrapolated, latency is not.
- **Real-host crawling at high concurrency.** Deliberately not done (politeness); item 6
  used local mock hosts. Real hosts add robots crawl-delays and slower responses.
- **Production PostgreSQL settings.** Everything ran with this machine's default
  PostgreSQL memory settings and other heavy programs running; expect production to be
  faster on the same hardware.

## Admin page?

Not added. The admin console already shows the numbers that change day to day (slow
searches, availability, relevance judging). These results change only when someone reruns
a benchmark, so the JSON reports plus this file are enough; a page would be a second copy
to keep in sync.
