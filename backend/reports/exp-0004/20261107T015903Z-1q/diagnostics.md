# Developer's Eye | EXP-0004 Batch Search Diagnostics

Run: `20261107T015903Z-1q` | Queries: **1** | Corpus snapshot: {'text': {'N': 42114, 'avgDL': 672.1790395197598}, 'code': {'N': 42114, 'avgDL': 235.9502607095389}}

**Scope:** same retrieved candidate IDs, ranked by BM25 versus PostgreSQL 
`ts_rank_cd`. TITLE_HINT and language are heuristics, not human relevance 
grades. Rank agreement is not ranking quality. The corpus can change 
between queries while the crawler runs. This is not Recall@100, 
Precision@10, MRR@10 or nDCG@10.

Flags: ERROR: 1

## All queries

| ID | Category | Query | Mode | Candidates | Overlap | Time (ms) | Flags |
|---|---|---|---|---:|---:|---:|---|
| Q051 | JavaScript | javascript fetch examples | all | 0 | N/A | 12 | ERROR |

## Flagged queries

### Q051: javascript fetch examples

Mode: `all` | Flags: `ERROR` | Candidates: 0 | Time: 12 ms

Error: `ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) function ts_rank(double precision[], tsvector, tsquery, integer) does not exist
[SQL: SELECT anon_1.document_id, ts_rank(ARRAY[$1::FLOAT, $2::FLOAT, $3::FLOAT, $4::FLOAT], anon_1.search_vector`

## Next steps

1. Review flagged queries manually; flags are **leads**, not relevance verdicts.
2. Add independently judged document relevance labels (qrels).
3. Evaluate ranking quality with P@10, MRR@10 and nDCG@10; separately test candidate recall.
