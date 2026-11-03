---
id: ADR-0024
title: Use bounded PostgreSQL candidate retrieval before final ranking
status: accepted
date: '2026-11-02'
area: backend
feature: retrieval
code:
- backend/src/backend/search/retrieval/fts.py
- backend/src/backend/search/retrieval/code.py
- backend/src/backend/search/service.py
- backend/src/backend/models/search_index.py
supersedes: null
superseded_by: null
related:
- ADR-0003
- ADR-0010
- ADR-0026
---

# ADR-0024: Use bounded PostgreSQL candidate retrieval before final ranking

## TL;DR

Retrieve a bounded candidate set using the two GIN-indexed vectors. ts_rank_cd is a candidate ordering signal; it is not the proposed final BM25 score.

## Context

The first live API needed useful results before the modular ranking engine existed. Later code retrieval must fit that existing contract without accidentally double-counting code evidence.

## Decision

get_full_text_search currently searches BOTH vectors with websearch_to_tsquery (english/simple), ORs their matches and orders by summed ranks then document_id. It returns dictionaries, up to 100. search_code separately uses plainto_tsquery(simple), AND semantics, normalization 32 for ts_rank_cd, limit up to 100 and offset up to 10,000. It returns CodeRetrievalHit. These outputs require explicit adaptation to RetrievalHit before merge. No exact punctuation-preserving symbol index exists. GIN accelerates matching, not the subsequent rank sort by itself.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Postgres bounded candidate set | Reuses existing vectors and database | Candidate recall limits final ranking | chosen |
| Return every matching document to Python | Full candidate recall | Unbounded transfer and scoring cost | rejected |
| Treat current FTS as text-only | Convenient planner label | It also contributes code scores | rejected |
| External search engine immediately | Specialized features | Another index lifecycle without comparative evidence | deferred |

## Why

Candidate generation can be tested and measured independently of scoring. The actual channel behavior must be explicit before connecting a two-target planner.

## Consequences

- Gained: A working FTS baseline and a separate code retrieval component.
- Accepted limitations / tech debt: Post-filtered categories can underfill pages; offset pagination has cost and consistency limits. simple avoids stemming but still uses PostgreSQL tokenization.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Matching/search configurations agree with indexed vector configurations.
- Ties use document_id for deterministic ordering.
- No retriever claims its score is BM25.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/src/backend/search/retrieval/fts.py`](../../../backend/src/backend/search/retrieval/fts.py)
- [`backend/src/backend/search/retrieval/code.py`](../../../backend/src/backend/search/retrieval/code.py)
- [`backend/src/backend/search/service.py`](../../../backend/src/backend/search/service.py)
- [`backend/src/backend/models/search_index.py`](../../../backend/src/backend/models/search_index.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/tests/integration/test_fts.py`](../../../backend/tests/integration/test_fts.py)
- [`backend/tests/integration/test_code.py`](../../../backend/tests/integration/test_code.py)
- [`backend/tests/integration/test_search.py`](../../../backend/tests/integration/test_search.py)

## Revisit when

- Judged relevant documents fall outside the candidate cap.
- Deep offsets or rank sorting dominate query profiles.

## Rules for future changes

- Document whether a retriever contributes text, code or both.
- Add adapters and channel-contract tests before calling merge_hits.
