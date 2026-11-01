# Search API

Area: backend · Status: active

## Purpose
Serves public search: `GET /search` reads `search_index` and `document` and returns results in the shape the Next.js `/api/search` bridge expects. It does not write to the index or the vocabulary; the indexer owns both.

## Code
- `backend/src/backend/api/search.py`
- `backend/src/backend/search/` (service, retrieval; analyzer, planner, fuzzy, ranking are in progress)
- `backend/src/backend/schema/search.py`

## How-it-works docs
- `frontend/public/api-reference.md`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0003](ADR-0003-search-endpoint-on-postgres-fts.md) | decision | GET /search ranks Postgres FTS matches by summed ts_rank_cd | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] `websearch_to_tsquery`, summed `ts_rank_cd` and `ts_headline` snippets (ADR-0003)
- [ ] Analyzer → planner → text/code/fuzzy retrieval → merge → ranking pipeline (in progress)
- [ ] Relevance evaluation set before ranking tuning

## Open issues
- `search/retrieval/fuzzy/correction.py` imports `find_fuzzy_candidates` from `candidates.py`, which does not define it, and imports `get_exact_term` from itself. `candidates.py` holds the exact-lookup code. The fuzzy module cannot be imported yet.

## Rules for future changes
- Keep the FTS configs in `/search` equal to the indexer's (`english` / `simple`) (ADR-0003).
- Pass the query as a bound parameter; never log it (ADR-0003).
- Change `SearchResultOut` and `frontend/lib/search.ts` together (ADR-0003).
- Replacing the summed-rank ordering or adding pagination needs a new ADR (ADR-0003).
