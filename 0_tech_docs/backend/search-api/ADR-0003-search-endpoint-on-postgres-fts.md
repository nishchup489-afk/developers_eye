---
id: ADR-0003
title: GET /search ranks Postgres FTS matches on both vectors by summed ts_rank_cd
status: accepted
date: 2026-10-31
area: backend
feature: search-api
code:
  - backend/src/backend/api/search.py:search
  - backend/src/backend/search/service.py:search_documents
  - backend/src/backend/search/service.py:categorize
  - backend/src/backend/search/retrieval/fts.py:get_full_text_search
  - backend/src/backend/schema/search.py
supersedes:
superseded_by:
related: [ADR-0002]
---

# ADR-0003: GET /search ranks Postgres FTS matches on both vectors by summed ts_rank_cd

## TL;DR
`GET /search?q=&source=&limit=` runs one query against `search_index`: `websearch_to_tsquery('english', q)` against `search_vector` OR `websearch_to_tsquery('simple', q)` against `code_vector`, ranked by `ts_rank_cd(search_vector) + ts_rank_cd(code_vector)`, top 100. The service then loads the matching available documents, maps each to a public category, builds a `ts_headline` snippet, applies the category filter and cuts to `limit`. It is the simplest thing that serves the contract the frontend already had, using only the index the indexer already writes.

## Context
Until commit `e9e8726` (2026-10-30) the frontend's `/api/search` bridge had no backend to call and served demo results (`frontend/lib/demo.ts`). The index was already populated with two tsvectors per document (`english` for prose, `simple` for code tokens) and GIN indexes on both. The response shape was fixed by the frontend (`frontend/lib/search.ts`): `title`, `source` (one of `docs`, `github`, `stackoverflow`, `reddit`, `articles`, `events`, `practice`), `url`, `snippet`, `score`, `tags`, `type`.

Constraints: no new infrastructure, no ranking model yet, and no relevance test set to tune against.

## Decision
1. **Input.** `q` is at most 300 characters; whitespace is collapsed; an empty query or any Unicode control character (`Cc`) returns 422. `limit` is 1 to 50 (default 20). `Cache-Control: no-store`.
2. **Retrieval** (`get_full_text_search`, `limit=100`):
   - `text_query = websearch_to_tsquery('english', q)`, `code_query = websearch_to_tsquery('simple', q)`;
   - `WHERE search_vector @@ text_query OR code_vector @@ code_query`;
   - `ORDER BY ts_rank_cd(search_vector, text_query) + ts_rank_cd(code_vector, code_query) DESC, document_id ASC`.
   Both ranks use weight defaults and no normalization flag.
3. **Hydration** (`search_documents`): load `document` rows for those ids with `is_available = true`, skip URLs that are not `http`/`https`, and keep the retriever's order. The snippet is `ts_headline('english', description || left(body, 5000), websearch_to_tsquery('english', q), 'MaxWords=35,MinWords=15,ShortWord=2')` with no highlight markers.
4. **Category.** A known host wins (`github.com`/`gitlab.com` → `github`, `stackoverflow.com`/`stackexchange.com` → `stackoverflow`, `reddit.com` → `reddit`, LeetCode/HackerRank/Exercism/Codewars → `practice`). Otherwise the classifier's `document_type` maps (`documentation` → `docs`, `tutorial`/`blog` → `articles`, `question` → `stackoverflow`, `issue`/`repository` → `github`, `event` → `events`), defaulting to `articles`.
5. **Filtering and paging.** The `source` filter is applied in Python after hydration, to the top 100 candidates. There is no offset or cursor.
6. **Errors.** Any `SQLAlchemyError` returns 503 with a fixed message; the query text is not logged.

**Planned, not wired into `/search` yet:** the query analyzer (`search/query_analyzer/analyzer.py`, NFC, bidi-control rejection, length limits; 57 tests in `884d07c`), a query planner that picks text, code or both, code-only retrieval with `plainto_tsquery('simple')` (`search/retrieval/code.py`), fuzzy correction against `search_terms` (`search/retrieval/fuzzy/`), and the empty `merge.py`, `ranking/ranking.py`, `snippets.py`, `pagination.py`.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. One FTS query on both vectors, summed `ts_rank_cd`, filter after hydration | One round trip for ranking; uses existing GIN indexes; no new code paths | Scores from two configs are added as if comparable; category filter can return fewer than `limit` | chosen |
| B. Separate text and code queries merged in Python (the planned pipeline) | Each side can be ranked and limited on its own; mode `text`/`code` | More queries and a merge step to design | planned |
| C. External search engine (Elasticsearch, OpenSearch, Meilisearch) | BM25, fuzzy and highlighting built in | Another service to run and keep in sync with Postgres | rejected for now (see search-vectors) |
| D. `plainto_tsquery` instead of `websearch_to_tsquery` | Never treats input as syntax | No quoted phrases, `OR` or `-term` for users | rejected for `/search`; used in `code.py` |

> **Question for nish:** why `ts_rank_cd` (cover density) rather than `ts_rank`? And did you mean to add the two ranks with equal weight, or is that a placeholder until `ranking.py` exists?

> **Question for nish:** the handoff says the next step is "weight the two vectors, push the category filter into SQL, add pagination". Is that still the plan, or does the analyzer → planner → retrieval → merge → ranking pipeline replace this whole service?

## Why
- **Correctness.** `websearch_to_tsquery` cannot raise a syntax error on user input, and using the same configs as the indexer (`english`, `simple`) means a query lexeme matches the stored lexeme.
- **Performance.** Both `@@` predicates can use the GIN indexes on `search_vector` and `code_vector`. Hydration and `ts_headline` run on at most 100 rows, and `ts_headline` only sees the first 5,000 characters of the body.
- **Security.** All SQL is parameterized; control characters are rejected; the URL scheme check stops `javascript:` or `file:` links reaching the page; database errors don't leak details.
- **Cost to build.** About 150 lines, no new tables, no new process.

## Consequences
- Gained: live search instead of demo data, with no new infrastructure.
- Accepted limitations:
  - The two ranks are not normalized against each other, so a code-heavy page can outrank a better prose match (or the reverse).
  - A category filter only sees the top 100 overall matches. A rare category can return 0 results even though matches exist further down.
  - No pagination; `limit` caps at 50.
  - No typo tolerance; a misspelled word just returns fewer results.
  - Documents that became unavailable since indexing are filtered at hydration, so a page can be short until the indexer removes their rows.
- What depends on this: `frontend/app/api/search/route.ts` (calls `BACKEND_URL/search`), `frontend/lib/search.ts` (validates the response).

## Invariants
- The text side uses the same text search config as `search_vector`, and the code side the same config as `code_vector` (`english` and `simple`; see `INDEXER_TEXT_SEARCH_CONFIG`, `INDEXER_CODE_SEARCH_CONFIG`).
- Only `document.is_available = true` rows with an `http`/`https` URL are returned.
- Order is score descending, then `document_id` ascending, so equal scores are stable between requests.
- The response matches `SearchResponseOut`, which must stay in step with `frontend/lib/search.ts`.

## Evidence
- Tests:
  - `backend/src/backend/tests/api/test_search_route.py`: results shape, 422 on bad input, 503 on database error.
  - `backend/src/backend/tests/integration/test_search.py` (Postgres, `TEST_DATABASE_URL`): frontend-shaped results, unavailable documents hidden, category filter and limit, no-match returns empty, `categorize()` table.
  - `backend/src/backend/tests/integration/test_fts.py` (25 tests, `563b83d`).
- Measured: nothing yet. No latency or relevance numbers.
- Commits: `bad199e` (FTS), `563b83d`, `e9e8726` (endpoint).

## Revisit when
- The 30-query relevance set from the checklist exists. Tune weights against it, not by eye.
- A category filter returns fewer than `limit` results while matching documents exist (move the filter into SQL).
- p95 `/search` latency goes over about 300 ms on the real index.

  > **Question for nish:** what latency target do you want for `/search`? 300 ms is a placeholder.
- The planned analyzer/planner/merge pipeline is wired in. That should be a new ADR that supersedes this one.

## Rules for future changes
- Keep the FTS configs in `/search` equal to the indexer's (`english` for `search_vector`, `simple` for `code_vector`).
- Do not interpolate the query into SQL; pass it as a bound parameter.
- Do not log the raw query.
- Change `SearchResultOut` and `frontend/lib/search.ts` in the same commit.
- Replacing the summed-rank ordering or adding pagination needs a new ADR.
- Keep passing: `tests/api/test_search_route.py`, `tests/integration/test_search.py`, `tests/integration/test_fts.py`.
