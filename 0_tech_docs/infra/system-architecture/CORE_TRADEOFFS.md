P0: Search engine performance and relevance
	Trade-off	What to measure
☐	1. Custom BM25 vs PostgreSQL ts_rank	P@10, MRR@10, nDCG@10, p50/p95 latency
☐	2. Candidate retrieval depth (50, 100, 200, 500)	Recall@100, nDCG@10, latency, CPU
☐	3. Query complexity (1, 2, 5, 10 terms)	p50/p95 latency, query plans, CPU
☐	4. Search concurrency (1, 10, 25, 50, 100 users)	Requests/sec, p95/p99 latency, error rate
☐	5. Search timeout budget (1s, 2s, 5s)	Timeout rate, completed queries, resource usage

P1: Crawler and indexing performance
	Trade-off	What to measure
☐	6. Crawler concurrency (2, 8, 16, 32, 64 workers)	Docs/sec, HTTP 429/5xx, CPU, RAM
☐	7. Indexer batch size (25, 50, 100, 250, 500)	Docs/sec, transaction latency, memory
☐	8. Indexer concurrency (1, 2, 4, 8 workers)	Indexing throughput, lock waits, DB utilization
☐	9. Crawl + search simultaneously vs separately	Search p95 latency, crawling throughput, DB load
☐	10. Database connection pool size	Throughput, connection waits, errors, memory

P2: Storage, scalability and infrastructure
	Trade-off	What to measure
☐	11. Corpus scaling (10K, 50K, 100K documents)	Index size, search latency, RAM, disk
☐	12. PostgreSQL index alternatives	Query latency, storage, insert overhead
☐	13. Vocabulary/statistics refresh strategy	Write amplification, lock contention, freshness
☐	14. Local machine vs cloud VM	Latency, throughput, monthly cost
☐	15. Recrawl frequency	Content freshness, bandwidth, changed-page yield



-----



1. Custom BM25 vs PostgreSQL ts_rank	P@10, MRR@10, nDCG@10, p50/p95 latency

```powershell
cd backend
poetry run python scripts/compare_rankings.py "FastAPI Depends" --mode all --k 10 --output reports/fastapi-ranking.json
```


---
result 
---

```
──────────────────────────────────────────────────────────────────────────────────────
  DEVELOPER’S EYE  BM25 vs PostgreSQL
──────────────────────────────────────────────────────────────────────────────────────
  QUERY  FastAPI Depends
  MODE   ALL     CANDIDATES  100
  TOP-10 OVERLAP  60.0%     AVG RANK SHIFT  16.74

  POSTGRESQL top-10: [17280, 19141, 21700, 21827, 6755, 22181, 22300, 22082, 21929, 65558]
  BM25       top-10: [65558, 21700, 22300, 22181, 17280, 21929, 15133, 25119, 20386, 14901]

──────────────────────────────────────────────────────────────────────────────────────
BM25#   PG#   DOC ID     BM25 SCORE       PG SCORE    CHANGE  TITLE
──────────────────────────────────────────────────────────────────────────────────────
    1    10    65558      38.063127       1.811144   +  9  fast-api-non-annotated-dependency (FAST002) | Ruff
    2     3    21700      37.466922       2.930949   +  1  Dependencies - FastAPI
    3     7    22300      37.415445       2.463805   +  4  Sub-dependencies - FastAPI
    4     6    22181      37.273011       2.540897   +  2  Global Dependencies - FastAPI
    5     1    17280      37.207095       4.517324     -4  Dependencies - Depends() and Security() - FastAPI
    6     9    21929      36.702380       2.378992   +  3  Dependencies in path operation decorators - FastAPI
    7    27    15133      36.651468       0.698826   + 20  Use Old 403 Authentication Error Status Codes - FastAPI
    8    20    25119      36.401776       1.113877   + 12  Security - First Steps - FastAPI
    9    21    20386      36.114531       1.007384   + 12  Background Tasks - FastAPI
   10    14    14901      35.894918       1.514256   +  4  FastAPI Security - OWASP Cheat Sheet Series
──────────────────────────────────────────────────────────────────────────────────────
  +N = promoted by BM25   -N = demoted by BM25   = = same rank
  Overlap measures agreement, not which ranking is more relevant.

Saved: reports\fastapi-ranking.json
```