# Public search API and integration boundary

Area: backend · Status: active

## Purpose

GET /search currently normalizes q locally, calls the dual-vector FTS retriever, loads available documents, maps public categories and emits ts_headline snippets. The analyzer/planner/merge/new-snippet/BM25 modules are not connected to this service.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/api/search.py`](../../../backend/src/backend/api/search.py)
- [`backend/src/backend/search/service.py`](../../../backend/src/backend/search/service.py)
- [`backend/src/backend/schema/search.py`](../../../backend/src/backend/schema/search.py)

## How-it-works docs

- [`backend/README.md`](../../../backend/README.md)
- [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0003](ADR-0003-search-endpoint-on-postgres-fts.md) | decision | GET /search ranks Postgres FTS matches on both vectors by summed ts_rank_cd | accepted |
| [ADR-0023](../query-planning/ADR-0023-pure-query-analysis-and-explicit-planning.md) | decision | Keep query normalization and retrieval planning pure and explicit | accepted |
| [ADR-0024](../retrieval/ADR-0024-bounded-postgres-candidate-retrieval.md) | decision | Use bounded PostgreSQL candidate retrieval before final ranking | accepted |
| [ADR-0026](../merge-and-contracts/ADR-0026-merge-channel-scores-by-document.md) | decision | Merge candidates by document ID while retaining independent channel evidence | accepted |
| [ADR-0028](../ranking/ADR-0028-candidate-bm25-ranking-plan.md) | decision | Introduce BM25 reranking only after statistics and relevance validation | proposed |
| [ADR-0029](../snippets/ADR-0029-plain-text-query-aware-snippets.md) | decision | Generate bounded plain-text passages with separate highlight offsets | accepted |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0028. Do not mark them accepted solely because this overview exists.

## Open issues

The route uses a 300-character limit while the analyzer defaults to 256 normalized characters; retrieval output types require adapters. Fuzzy correction has the import defect in INC-0008. Category filtering happens after a 100-candidate cap; there is no implemented total-count/pagination pipeline.

## Rules for future changes

- Keep the FTS configs in `/search` equal to the indexer's (`english` / `simple`) (ADR-0003).
- Pass the query as a bound parameter; never log it (ADR-0003).
- Change `SearchResultOut` and `frontend/lib/search.ts` together (ADR-0003).
- Replacing the summed-rank ordering or adding pagination needs a new ADR (ADR-0003).
- Reconcile the frontend, route and analyzer contracts in one integration change.
- Do not call the query analyzer a PostgreSQL tokenizer.
- Document whether a retriever contributes text, code or both.
- Add adapters and channel-contract tests before calling merge_hits.
- Add explicit retriever-to-RetrievalHit adapters.
- Preserve order independence, input immutability and duplicate-hit idempotence in tests.
- Record formula and normalization semantics before implementing scoring.
- Evaluate candidate recall as well as final ranking quality.
- Supersede ADR-0003 only when the public ranking behavior actually changes.
- Render snippet content as text, not trusted HTML.
- Generate snippets after final top-result selection.
- Preserve the hard character cap when improving word/line boundaries.
