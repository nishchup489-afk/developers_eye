---
id: EXP-0008
title: Measure crawl, index and search capacity for a 2M document target
status: done
outcome: adopt
date: '2026-11-05'
area: infra
feature: performance-and-scaling
informs:
- ADR-0042
- ADR-0043
---

# EXP-0008: Measure crawl, index and search capacity for a 2M document target

## Question

Can one server crawl politely with several processes, index fast enough to rebuild 2M documents in a day, and answer searches inside the 3 second deadline at 2M documents?

## Why it matters

These numbers decide whether the single-server plan on Oracle Always Free holds, and they are the evidence for ADR-0042 and ADR-0043.

## Setup

- Windows 11 laptop, Python 3.14, PostgreSQL 18.3 with default settings. These are development numbers, not Oracle ARM numbers.
- No request left the machine: the crawl harness fakes DNS and HTTP with about 80 ms of latency.
- Search corpus: 2,000,000 synthetic documents of 300 words, drawn from only 40 common words plus one rarer token. No code vectors.

## Method

- Baseline: code before commit `800ab2b` for the crawl, before `5196c07` for the indexer.
- Variable: process count, concurrency, and the new designs.
- Metrics: merged request logs across processes, an exact recount of `search_terms`, search time with cold and warm DF cache.
- Runs: one run per crawl and index variant, five per search query. Crawl runs last 15 seconds, so treat them as direction, not precise rates.

## Reproduce

From `crawler/`, with `BENCH_DATABASE_URL` set to a migrated disposable database:

```bash
python tests/benchmarks/fake_web_load.py --workers 4 --concurrency 50 --hosts 200 --pages 30 --gap 0.5 --seconds 15
python tests/benchmarks/bench_indexer.py --documents 3000 --levels 4 --processes 4
python tests/benchmarks/bench_search.py --documents 2000000 --rounds 5
```

## Results

Crawl, 0.5 second gap per host:

| Code | Processes | Hosts | Requests/s | Limit | Gap violations |
| --- | --- | --- | --- | --- | --- |
| Before | 1 | 10 | 19.5 | 20 | 0 |
| Before | 4 | 10 | 78.6 | 20 | 1,151 of 1,161 |
| Before | 8 | 10 | 136.4 | 20 | 1,674 of 1,684, plus Postgres out of connections |
| Before | 1 (100 slots) | 200 | 47.8 | 400 | 0 |
| After | 4 | 10 | 15.7 | 20 | 0 |
| After | 8 | 10 | 16.0 | 20 | 0 |
| After | 1 (100 slots) | 200 | 61.9 | 400 | 0 |
| After | 4 (50 slots each) | 200 | 204.5 | 400 | 0 |
| After, with 429s | 4 | 20 | 29.3 | 40 | 0 |

Index, 400 word documents:

| Code | Processes | Concurrency | Documents/s | Wrong counts |
| --- | --- | --- | --- | --- |
| Global lock | 1 | 1, 2, 4, 8 | 56 to 66 | 0 |
| Outbox | 1 | 1, 2, 4, 8 | 150 to 161 | 0 |
| Outbox | 1 | 4 | 170 | 0 |
| Outbox | 4 shards | 4 | 581 | 0 |

Search at 2,000,000 documents, milliseconds, median of 5 (slowest in brackets):

| Query | Cold DF cache | Warm DF cache |
| --- | --- | --- |
| One very common word | 773 (3,457) | 212 (388) |
| Two very common words | 1,714 (1,984) | 303 (395) |
| Rare word | 14 (81) | 11 (18) |
| Rare and common word | 1,061 (1,202) | 28 (45) |
| Common word with a source filter | 1,036 (1,081) | 350 (394) |
| No match | 1 (2) | 1 (1) |

Corpus statistics took 1.5 seconds for both channels. Database size was 5.2 GB, which understates real data because the synthetic vocabulary is tiny.

## Analysis

- The gap sits below its limit because it is now measured from the end of a request, as intended.
- One process tops out near 60 requests/s and 170 documents/s. Both are Python limits, so more processes are what scale, not more slots.
- 581 documents/s rebuilds 2M documents in about an hour on this machine. GIN inserts slow down as the index grows, so expect less at full size.
- The word list is a worst case for search: most documents match the common words. The remaining cost is counting DF on a cache miss, which the 10 minute cache hides. The slowest cold query went past the 3 second deadline, so it would return 503 once.
- This run found a real bug: the sampled statistics query failed above 20,000 documents, which would have stopped the API at startup. Small test databases never reached that path.

## Outcome

Adopted. The single-server plan holds for crawl and index. Search works but cold common-term queries are too close to the deadline, so seed DF from `search_terms` or precompute top terms before launch.

## Not measured

Oracle ARM hardware, real pages, code vectors, search during heavy ingestion, or more than one user at a time. Run these on the real server before calling load testing done.
