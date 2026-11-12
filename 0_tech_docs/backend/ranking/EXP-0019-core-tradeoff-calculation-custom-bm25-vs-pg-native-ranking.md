---
id: EXP-0019
title: Custom BM25 against PostgreSQL ts_rank_cd on the same candidates, relevance and latency
status: done
outcome: inconclusive
date: 2026-11-12
area: backend
feature: ranking
informs: [ADR-0028, ADR-0057]
---

# EXP-0019: Custom BM25 vs PostgreSQL native ranking

## Question
On the live 100K corpus, the custom candidate BM25 gives better P@10, MRR@10 and nDCG@10 than
PostgreSQL `ts_rank_cd` over the same candidates, at an acceptable latency cost.

## Why it matters
BM25 adds DF counts and TF/DL loads to every search (INC-0041, EXP-0016). If it does not rank better,
that work buys nothing. Trade-off 1 of [CORE_TRADEOFFS.md](../../../CORE_TRADEOFFS.md).

## Setup
- Hardware / OS: Intel Core Ultra 7 265F (20 cores), 32 GB, NVMe, Windows 11. The user's crawler was
  writing to the real database on the same server; the machine had 30+ GB RAM in use.
- Versions: PostgreSQL 18.3 with default settings (shared_buffers 128 MB), Python 3.14.4.
- Data: `developers_eye_bench`, a pg_dump copy taken 2026-11-12 (100,141 indexed documents).
- Labels: the 25-query, 328-grade AI-reviewed set from EXP-0014. The human judging tables (ADR-0057)
  had 467 pooled rows and 0 grades, so they could not be used.

## Method
- Baseline: PostgreSQL `ts_rank_cd` order (the `compare_rankings.py` expression) over the candidates.
- Variable changed: the live BM25 (`rank_candidates`, metadata filter) over the identical candidates.
- Metrics: P@10, MRR@10, nDCG@10 (unjudged URLs count as grade 0, judged share reported); p50/p95 of
  retrieval + ranking, cold and warm DF cache.
- Runs per variant: 25 queries x 5 rounds x {cold, warm}.

## Reproduce
```
crawler\.venv\Scripts\python.exe backend\scripts\tradeoffs\search_bench.py ranking --rounds 5
```
Raw: `backend/reports/tradeoffs/01-ranking-bm25-vs-pg.json`. Method: `guide/tradeoffs_calculation.md`.

## Results
| Ranker | P@10 | MRR@10 | nDCG@10 | Top 10 graded | p50 cold | p95 cold | p50 warm | p95 warm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.708 | 0.900 | 0.693 | 96.8% | 146 ms | 674 ms | 45 ms | 386 ms |
| PostgreSQL | 0.780 | 0.927 | 0.689 | 100% | 16 ms | 426 ms | 13 ms | 309 ms |
| Retrieval only | | | | | 11 ms | 421 ms | 10 ms | 306 ms |

## Analysis
The claim is not supported: nDCG ties, PostgreSQL wins P@10 and MRR, and BM25 costs about 130 ms more
at the cold median (DF counts) and 32 ms warm. p95 is dominated by retrieval for both. Limits: AI grades,
not human ones; 3.2% of BM25's top 10 was never graded; background load on the machine.

## Outcome
Inconclusive until human grades exist. Next: grade the 36 human queries on the admin Search quality page and
rerun the script. Question for nish: if humans agree with these numbers, do you want to switch final
ranking to `ts_rank_cd` and keep BM25 only as a diagnostic?
