# How the core trade-off numbers were calculated

This guide explains, step by step, where every number in
[`CORE_TRADEOFFS.md`](../CORE_TRADEOFFS.md) comes from, so you can check it,
rerun it, or run it again on the Oracle VM. Every number is in a JSON report in
[`backend/reports/tradeoffs/`](../backend/reports/tradeoffs/), and every report
was written by one script in [`scripts/tradeoffs/`](../scripts/tradeoffs/).

**In one paragraph:** each trade-off is a script that runs the real code
(search service, API, crawler, indexer) on a copy of your database, times every
operation, reads CPU and memory from the operating system while it runs, and
writes a JSON report. CORE_TRADEOFFS.md is those reports turned into tables. The
sections below show, for each item, what was run, what was counted, and one
number recomputed by hand from its report.

## 0. Before you start

### 0.1 Which Python

There is no `.venv` at the repository root. Use the crawler's environment,
because it has the backend, the crawler and the indexer installed together:

```powershell
crawler\.venv\Scripts\python.exe -m pip install psutil   # once; the CPU/RAM sampler needs it
crawler\.venv\Scripts\python.exe scripts\tradeoffs\search_bench.py ranking
```

(The backend's own Poetry environment works for the search-only scripts, but
not for the crawler and indexer ones.)

### 0.2 Never on the real database: make a copy

Several benchmarks write (indexer runs, mock crawls, schema copies), so every
script refuses any database whose name does not start with
`developers_eye_bench` (set `BENCH_ALLOW_ANY_DB=1` only for read-only runs).
Make the copy with plain PostgreSQL tools. `pg_dump` reads a consistent
snapshot, so the crawler can keep running while it copies:

```powershell
pg_dump -h localhost -U postgres -Fc -Z1 -f de.dump developers_eye
psql -h localhost -U postgres -c "create database developers_eye_bench"
pg_restore -h localhost -U postgres -d developers_eye_bench -j 8 de.dump
psql -h localhost -U postgres -d developers_eye_bench -c "analyze"
```

On this machine that took 2 min 35 s for the 2.4 GB database. The scripts find
the copy by taking `DATABASE_URL` from `backend/.env` and swapping the database
name, or you can pass `--database-url` or set `BENCH_DATABASE_URL`.

### 0.3 Run everything

```bash
PY=crawler/.venv/Scripts/python.exe; S=scripts/tradeoffs
$PY $S/search_bench.py ranking --rounds 5                         # 1
$PY $S/search_bench.py depth --rounds 3                           # 2
$PY $S/search_bench.py complexity --rounds 5                      # 3
$PY $S/http_bench.py concurrency --seconds 20                     # 4
$PY $S/http_bench.py timeout --users 25 --seconds 30              # 5
$PY $S/crawl_bench.py workers --workers 2 8 16 32 64 --seconds 45 # 6
$PY $S/indexer_bench.py batch --docs 3000                         # 7
$PY $S/indexer_bench.py concurrency --docs 3000                   # 8
$PY $S/indexer_bench.py processes --docs 3000                     # 8 (processes)
$PY $S/crawl_bench.py mixed --workers 16 --users 10 --seconds 30  # 9
$PY $S/crawl_bench.py pool --tasks 25 --seconds 20                # 10
$PY $S/storage_bench.py scaling --rounds 3                        # 11
$PY $S/storage_bench.py indexes                                   # 12
$PY $S/indexer_bench.py vocabulary --docs 2000                    # 13
$PY $S/cloud_estimate.py                                          # 14 (reads the others)
$PY $S/crawl_bench.py recrawl                                     # 15
```

Run them one after another, never two at once, or they slow each other down.
The whole set takes about 45 minutes here.

## 1. The measuring tools every script shares

All of these live in [`common.py`](../scripts/tradeoffs/common.py).

### 1.1 Latency percentiles

Every timed operation is one sample in milliseconds, taken with
`time.perf_counter()` immediately before and after the call. The percentiles are
"nearest rank": sort the samples, and p95 is the sample at position
`ceil(0.95 × n)` (counting from 1).

Example: 25 samples sorted. `ceil(0.95 × 25) = ceil(23.75) = 24`, so p95 is the
24th-smallest sample, and p99 is `ceil(24.75) = 25`, the largest. With small
sample counts p99 is simply the maximum, which is why the reports always print
`n` next to the percentiles.

### 1.2 CPU: "cpu seconds" and "cores"

`ResourceSampler` reads each process's total CPU time (user + system) from the
operating system at the start and end of a run:

- `python_cpu_seconds`: this Python process and its children (for HTTP tests,
  the uvicorn server process is added), minus the sampler thread's own CPU.
- `postgres_cpu_seconds`: every `postgres.exe` process. A backend that ends
  during the run keeps its last reading; one that starts counts from zero.
- `system_cpu_seconds`: the whole machine (all 20 cores).

`cores = cpu_seconds / wall_seconds`. A value of 0.5 means half of one core was
busy on average, 2.0 means two whole cores.

Per-operation CPU is `cpu_seconds / operations`. Example: 2.4 s of PostgreSQL
CPU over 300 searches is `2.4 / 300 = 8 ms` of database CPU per search.

**Background load warning.** These runs happened while your real crawler was
crawling into the real database on the same PostgreSQL server. PostgreSQL CPU
therefore includes that crawler's sessions. Every report has an
`idle_baseline` or the cloud estimate subtracts the idle PostgreSQL rate
(cores while the benchmark itself does nothing) before dividing.

### 1.3 Memory

The sampler reads resident memory (RSS) every 0.5 s (PostgreSQL every 2 s) and
keeps the peak: `peak_python_rss_mb`, `peak_postgres_rss_mb` (sum over all
postgres processes, so shared buffers count once per process that touched them;
read it as an upper bound) and `peak_system_used_mb`.

### 1.4 Relevance metrics

Relevance uses the 25 queries and 328 grades in
[`backend/evaluation/checklist-25/`](../backend/evaluation/checklist-25/README.md).
**These grades were made by an AI reviewer (EXP-0014), not by a person.** The
human judging page (ADR-0057) has 467 pooled candidates for 36 queries, but
**zero human grades so far**, so it could not be used. When you grade them, rerun
item 1 with those grades.

Grades: 0 irrelevant, 1 marginal, 2 useful, 3 ideal. A result URL nobody graded
counts as 0, and the report says what share of the top 10 had a grade
(`judged_share_of_top10`), so you can see how much was assumed.

For one query, with the top 10 URLs in order:

- **P@10** = (number of top-10 URLs with grade > 0) / 10. Missing positions count
  as not relevant, so a query that returns 3 results can score at most 0.3.
- **MRR@10** = 1 / (rank of the first URL with grade > 0), or 0 if none in the top 10.
- **nDCG@10** = DCG / IDCG, where DCG = Σ (2^grade − 1) / log2(rank + 1) over
  ranks 1..10, and IDCG is the same sum for the best possible order of all
  graded-positive URLs for that query.

Worked nDCG example: grades by rank are 3, 0, 2. DCG = (2³−1)/log2(2) +
0 + (2²−1)/log2(4) = 7/1 + 3/2 = 8.5. If the query's positives are {3, 2, 1},
IDCG = 7/1 + 3/log2(3) + 1/2 = 7 + 1.893 + 0.5 = 9.393. nDCG = 8.5 / 9.393 = 0.905.

The suite number is the plain average over queries (macro average). Queries
with no graded positives are left out of nDCG.

## 2. Item by item

### Item 1: BM25 vs PostgreSQL ranking

Script: `search_bench.py ranking`. Report: `01-ranking-bm25-vs-pg.json`.

1. For each of the 25 checklist queries, run the live retrieval (text, code and
   title channels, 100 per channel). This produces one candidate list.
2. Rank that same list twice: once with the live BM25 (`rank_candidates` plus the
   metadata filter), once with PostgreSQL `ts_rank_cd` (an `ORDER BY` in SQL, the
   same expression `compare_rankings.py` uses).
3. Time three things separately with `perf_counter`: retrieval, BM25 ranking, PG
   ranking. "BM25 latency" = retrieval + BM25 ranking; "PG latency" = retrieval + PG ranking.
4. Repeat 5 times with the DF cache cleared before each query (cold) and 5 times
   reusing it (warm): 125 samples per number.
5. Score both top-10 lists against the grades (section 1.4) and average over queries.

Check one number yourself: in the report, `latency.cold.bm25.p50_ms` is 146.3 and
`latency.cold.retrieval.p50_ms` is 10.8, so the cold BM25 ranking step costs about
146 - 11 = 135 ms at the median, almost all of it document-frequency counts for
query terms that are not in the cache yet.

### Item 2: candidate depth

Script: `search_bench.py depth`. Report: `02-candidate-depth.json`.

The same retrieval SQL as the live code, with the per-channel `LIMIT` set to 50,
100, 200 or 500 (the live functions refuse more than 100, so the benchmark runs
their SQL directly and raises the ranker's 256-candidate guard in its own process only).
For each query:

- **Judged Recall@100** = (graded-relevant URLs in BM25's top 100) / (all
  graded-relevant URLs for the query). Example: 8 known relevant pages, 7 in the
  top 100, gives 7/8 = 0.875. Averaged over queries.
- **Candidate recall** is the same over the whole candidate pool, before ranking.
- **CPU per query** = cpu seconds / (25 queries x 3 rounds). Example: 82 ms of
  PostgreSQL CPU at depth 100 is `postgres_cpu_seconds / 75`.

Recall only knows the pages someone graded. A deeper pool can surface relevant pages
nobody graded, which count as misses; that is why `judged_share_of_top10` is in the
report (0.97 at depth 100, 0.92 at 500).

### Item 3: query complexity

Script: `search_bench.py complexity`. Report: `03-query-complexity.json`.

Eight queries of each length (1, 2, 5, 10 words; listed in the report) through the
full `search_documents()`, 5 rounds cold + 5 warm = 80 samples per length. The plan
comes from `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` of the text-match statement for
the first query of each length; the report keeps the plan tree (`nodes`). "Mean
candidates" is the size of the merged candidate list before ranking.

### Item 4: search concurrency

Script: `http_bench.py concurrency`. Report: `04-search-concurrency.json`.

1. Start uvicorn the way production does (one worker) on the copy.
2. Warm it up for 10 s with 4 users.
3. For each level start N "users". Each user loops: pick a random query, send
   `GET /search`, wait for the answer, repeat at once. Stop after 20 s.
4. Count every response by status code and keep its latency.

- **Requests/s** = all responses / window seconds. Example, 25 users (run 2):
  1,314 responses / 20.6 s = 63.9/s.
- **Successful/s** = HTTP 200 only: 506 / 20.6 = 24.6/s.
- **Error rate** = (all - 200s) / all = 808 / 1,314 = 61%.
- **Database CPU per search** = PostgreSQL cores x window / successful searches =
  6.95 x 20.6 / 506 = 0.28 s.

The API's CPU is read from the uvicorn process *and its children*: on Windows a venv
`python.exe` is a small launcher that runs the real interpreter as a child. The first
run missed this, which is why the report was regenerated (run 1's latency numbers
are kept in CORE_TRADEOFFS.md for comparison).

### Item 5: timeout budget

Script: `http_bench.py timeout`. Report: `05-timeout-budget.json`.

A fresh server per budget, started with `SEARCH_QUERY_DEADLINE_MS` = 1000, 2000,
5000 and `SEARCH_TOTAL_DEADLINE_MS` one second higher, then 25 users for 30 s.

- **Timeout rate** = HTTP 504 / all responses. Example: 1 / 1,865 = 0.05% at 1 s.
- **Completed queries** = number of HTTP 200 responses.

### Item 6: crawler concurrency

Script: `crawl_bench.py workers` with `mock_hosts.py`. Report: `06-crawler-concurrency.json`.

No real website is contacted. `mock_hosts.py` listens on 127.0.0.1:80 and answers
for 64 made-up hosts `h00.bench` to `h63.bench` with realistic pages (40-250 ms each,
3-8 KB of docs-like HTML). It answers **429** if one host is hit twice within 1 s
(that would be a politeness bug) and **503** when more than 24 requests are in
flight (a site under strain).

The real crawler runs in-process: claim from the frontier, robots.txt, the shared
per-host politeness (one request in flight and 2 s between requests per host),
fetch, parse, process, write. Two checks are relaxed in that process only: DNS for
`*.bench` answers 127.0.0.1, and the "public IP only" rule accepts 127.0.0.1.

1. Warm-up: fetch every host's robots.txt once, so runs measure steady state.
2. For each worker count, queue fresh pages on all 64 hosts, crawl for 45 s, then
   park whatever was not reached, including leases the cancelled run left (they
   would otherwise hold their hosts for 5 minutes and starve the next run).
3. **Docs/s** = new document rows for that run's pages / 45 s.
4. **Politeness ceiling** = hosts / seconds between requests = 64 / 2 = 32 pages/s.
   No crawler setting can go above it without being impolite.
5. **429s and 503s** come from the mock's counters; `smallest_gap_seconds` is the
   shortest time between two requests to one host (it must stay at 2 s or more).

### Item 7: indexer batch size

Script: `indexer_bench.py batch`. Report: `07-indexer-batch-size.json`.

1. Pick 3,000 indexed documents at random (fixed seed, the same ones every run).
2. Delete their `search_index` rows so the indexer rebuilds them like new pages.
3. Run the real indexer code over them in batches (`_process_index` under the
   semaphore, then `drain_vocabulary_changes`, exactly as `run_worker` does); only
   the candidate list is given instead of found by the selection scan.
4. Measure:
   - **Docs/s** = 3,000 / run seconds. Example: 3,000 / 37.8 s = 79.4 at batch 500.
   - **Transaction latency** = each document's `duration_ms` (load, analyze, build,
     write under `FOR UPDATE`).
   - **Row writes per doc** = change in `pg_stat_user_tables` (inserts + updates +
     deletes) of `search_terms` / 3,000. Example: 144,902 / 3,000 = 48.
   - **WAL per doc** = `pg_wal_lsn_diff` between start and end / documents.
   - **Lock waits**: a separate connection polls `pg_stat_activity` every 50 ms and
     counts this database's sessions whose `wait_event_type` is `Lock`.

### Item 8: indexer concurrency

Same as item 7 with batch 200 and concurrency 1, 2, 4, 8 inside one process
(`08-indexer-concurrency.json`), and separately 1, 2, 4 **processes** that split
the same 3,000 documents by `id % processes`, like `INDEXER_SHARD_*`
(`08b-indexer-processes.json`). "DB utilization" is PostgreSQL CPU cores during the run.

### Item 9: crawl and search together

Script: `crawl_bench.py mixed`. Report: `09-crawl-and-search.json`. Three 30 s phases
against the same API server and mock hosts: 10 search users alone, a 16-worker crawl
alone, then both at once. Compare search p95, crawl docs/s and PostgreSQL CPU ("DB load").

### Item 10: connection pool size

Script: `crawl_bench.py pool`. Report: `10-connection-pool.json`.

Each pool size runs in a fresh child process (the engine reads `DB_POOL_SIZE` and
`DB_MAX_OVERFLOW` once). 25 tasks search in a loop for 20 s, each with its own
session. The benchmark wraps SQLAlchemy's pool `_do_get` in a timer, so
**checkout wait** is how long a task waited for a free connection.
**Searches/s** = completed / wall seconds. Errors are pool timeouts (5 s) or
statement timeouts (3 s).

The connection budget is plain arithmetic: processes x (pool_size + max_overflow)
per component, summed, against `max_connections` (100).

### Item 11: corpus scaling

Script: `storage_bench.py scaling`. Report: `11-corpus-scaling.json`.

1. For 10K and 50K, copy that many `search_index` rows into schema `c10000` /
   `c50000` (rows chosen by `md5(document_id)`, so the same sample every time) and
   create the same four indexes.
2. Point search at the sample with `SET search_path TO c10000, public` on every new
   connection, so the real `search_documents()` runs against it.
3. 12 queries x 3 rounds, cold and warm.
4. Sizes from `pg_relation_size` (heap and each index) and `pg_total_relation_size`;
   TOAST = total - heap - indexes (that is where the large tsvectors live).

The 2M row is arithmetic, labelled as an estimate: MB per 1,000 docs =
1,125.1 / 96.941 = 11.6, so 2,000 x 11.6 MB = 23,200 MB, about 22.7 GB. Latency is
deliberately **not** extrapolated: the 20K candidate pool cap changes the curve.

### Item 12: index alternatives

Script: `storage_bench.py indexes`. Report: `12-index-alternatives.json`.

Copy `search_index` into schema `idx` without indexes, then for each variant: build
the index (timed), `ANALYZE`, read its size, run the retrieval match query for 12
queries x 3 rounds (after one warm-up each), note the plan PostgreSQL chose, then
delete 2,000 rows and insert them back in batches of 100 with the index present.
**Insert cost per row** = insert seconds / 2,000.

### Item 13: vocabulary refresh

Script: `indexer_bench.py vocabulary`. Report: `13-vocabulary-refresh.json`.

- **Outbox (current):** index 2,000 documents normally (queue, then drain per batch).
- **Direct upsert:** for each of the same 2,000 documents, in its own transaction,
  `INSERT ... ON CONFLICT DO UPDATE SET document_frequency = document_frequency + 1`
  for each of its vocabulary terms (terms sorted, so no deadlocks), 4 at a time.
- **Full rebuild:** `indexer.vocabulary_rebuild.rebuild_vocabulary` over every document.

Write amplification = `search_terms` row writes / documents. Example (direct):
431,010 / 2,000 = 215. Outbox freshness = time until a document's terms are counted =
the drain after its batch (p95 1.1 s).

### Item 14: local vs Oracle ARM (estimate)

Script: `cloud_estimate.py`. Report: `14-local-vs-cloud.json`. It reads the other
reports and measures nothing. For search, step by step:

1. Local CPU per search = (API CPU + PostgreSQL CPU - idle PostgreSQL CPU) /
   successful searches, at the best level of item 4.
2. ARM CPU per search = local / `arm_per_core`. `arm_per_core` is how fast one Ampere
   A1 core is compared with one core here; default **0.45**, an assumption from public
   single-thread benchmark ratios (plausible range 0.35-0.55). Once the VM exists,
   run any of these scripts there and replace it with a measured ratio.
3. ARM searches/s = (4 OCPU x 0.7 target utilisation) / ARM CPU per search.
4. ARM latency range = local latency (if the work is I/O-bound) up to local / 0.45
   (if fully CPU-bound).
5. Monthly cost. Always Free = $0 inside the free shape. Pay-as-you-go for the same
   shape = (4 x $0.01 per OCPU-hour + 24 x $0.0015 per GB-hour) x 730 h = $55.48.
   Local electricity = 110 W x 730 h / 1000 x $0.16 per kWh = $12.85. All four prices
   are command-line parameters; check them before relying on them.

The same steps with "crawled page" or "indexed document" in place of "search" give
the crawl and index rows.

### Item 15: recrawl frequency

Script: `crawl_bench.py recrawl`. Report: `15-recrawl-frequency.json`. Read-only,
from the real crawl history in the copy.

1. Find page targets fetched successfully exactly twice (1,354), and the mean time
   between their two fetches (72.7 h).
2. A page **changed** if its document's `updated_at` moved at the second fetch (the
   writer only moves it when stored content changed): 212 of 1,354 = 15.66%.
3. Fit one change rate, assuming pages change randomly and independently (a Poisson
   process): rate = -ln(1 - 0.1566) / 72.7 h = 0.00234 per hour = 0.056 per day,
   one change every 17.8 days on average.
4. For a recrawl interval T hours, with x = rate x T:
   - changed-page yield = 1 - e^(-x), the share of recrawls that find a change.
     At 7 days: x = 0.00234 x 168 = 0.393, yield = 1 - e^-0.393 = 32.5%.
   - mean stale share = 1 - yield / x, the average share of pages whose stored copy is
     out of date at a random moment: 1 - 0.325 / 0.393 = 17.3%.
   - fetches per month per 100K docs = 100,000 x 720 / T; bandwidth = fetches x 160 KB.

## 3. Reading the numbers honestly

- One machine, one run per configuration (two for items 4 and 5), with other work
  running. Throughput differences under about 20% are within noise here.
- The local PostgreSQL runs with default memory settings; production's are far larger.
- Relevance uses AI grades. Latency and throughput do not depend on grades.
- With the Oracle VM, run the same commands there and replace the item 14 estimate
  with measurements.

## 4. Why there is no admin page for this

The admin console already shows the live numbers that change day to day (slow
searches, availability, relevance judging). These trade-off results are one-off
experiments that change only when someone reruns a benchmark, so a markdown table
plus the JSON reports is enough; an admin page would be a second copy to keep in sync.
The one live input these results need, human relevance grades, already has its page
(admin Search quality).
