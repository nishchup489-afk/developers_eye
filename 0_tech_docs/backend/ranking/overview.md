# BM25 ranking and relevance evaluation

Area: backend · Status: implemented ranking; evaluation in progress

## Current behavior

The live search pipeline retrieves up to 100 TEXT and 100 CODE candidates,
merges by document ID, reranks using custom BM25, then filters metadata,
paginates and renders snippets. Term frequencies, document frequencies and
document lengths are obtained from PostgreSQL TSVECTOR statistics; cached
corpus statistics are refreshed separately from the request path. Query
tokenization uses PostgreSQL English/Simple configurations.

The source contract and tests are the authoritative description, not the
older planning snapshot that predated the BM25 integration.

## Key code

- [BM25 formula](../../../backend/src/backend/search/ranking/bm25.py)
- [Ranking orchestration](../../../backend/src/backend/search/ranking/orchestrator.py)
- [Online search orchestration](../../../backend/src/backend/search/service.py)
- [Judged relevance metrics](../../../backend/src/backend/search/evaluation/metrics.py)
- [35-query benchmark manifest](../../../backend/evaluation/queries.json)
- [Relevance lab and score goldens](../../../backend/evaluation/README.md)

## Records

| ID | Type | Description | Status |
| --- | --- | --- | --- |
| [ADR-0028](ADR-0028-candidate-bm25-ranking-plan.md) | architecture | Original candidate BM25 design (retrospective plan) | proposed, historical |
| [EXP-0004](EXP-0004-lexical-relevance-evaluation.md) | experiment | Strictly judged BM25 vs PostgreSQL comparison | running, results pending |

## Verification and open gates

- Custom scorer and PostgreSQL comparison run on the same candidate set.
- Deterministic synthetic golden tests document expected BM25 score/order.
- Evaluation supports known-positive candidate recall (100 per channel),
  P@10, MRR@10, nDCG@10, no-result rate and per-query diagnostics.
- **Not yet established:** independently judged live results or quality win,
  complete-corpus Recall@100, or ranking safety under the unordered 20k
  preliminary retrieval pool.
- Do not claim that BM25 improves relevance from overlap or synthetic tests.
