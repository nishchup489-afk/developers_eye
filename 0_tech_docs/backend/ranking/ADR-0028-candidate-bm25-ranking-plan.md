---
id: ADR-0028
title: Introduce BM25 reranking only after statistics and relevance validation
status: proposed
date: '2026-11-02'
area: backend
feature: ranking
code:
- backend/src/backend/search/ranking/bm25.py
- backend/src/backend/search/ranking/ranking.py
- backend/src/backend/search/ranking/types.py
- backend/src/backend/search/service.py
supersedes: null
superseded_by: null
related:
- ADR-0003
- ADR-0026
- ADR-0027
- EXP-0004
---

# ADR-0028: Introduce BM25 reranking only after statistics and relevance validation

## TL;DR

The intended next stage is a pure BM25 scorer plus a ranking orchestrator over merged candidates. Both implementation files are empty at this snapshot; the live service still uses summed ts_rank_cd.

## Context

The project wants rarity, term-frequency saturation and length normalization in a transparent lexical ranker. The current types and statistics prepare that work but do not deliver a ranking engine.

## Decision

Planned responsibilities: statistics.py loads data, bm25.py computes a pure per-channel score, ranking.py combines channels and returns deterministic RankedHit values. Current type defaults are k1=1.2, b=0.75 and text/code weights=1.0; they are starting parameters, not tuned results. Proposed positive-IDF variant:

$$
\mathrm{score}(D,Q)=\sum_{t\in Q}\ln\left(1+\frac{N-df(t)+0.5}{df(t)+0.5}\right)\frac{tf(t,D)(k_1+1)}{tf(t,D)+k_1(1-b+b\,dl(D)/avgdl)}
$$

N is the indexed corpus size for the channel definition; df counts documents, tf counts occurrences, dl is document length and avgdl is its corpus mean. Rarity raises IDF; repeated terms saturate. Define empty/zero-length behavior, positive query-lexeme extraction, negative/phrase handling, missing candidates and stale snapshots before integration. Weighting two channel scores is not automatically BM25F.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Candidate reranking with pure BM25 | Inspectable formula and separable I/O | Approximate stats and candidate truncation limit quality | proposed |
| Keep ts_rank_cd baseline | Already serves results | Different relevance model | retain as baseline/fallback |
| Neural reranker or embeddings first | Could improve semantic matches | Evaluation, latency and model operations unresolved | deferred |

## Why

A scorer is small; proving that its statistics and retrieved candidates match the query semantics is the harder requirement. Existing field-weighted PostgreSQL ranks must not silently become unweighted BM25 without evaluation.

## Consequences

- Gained: A testable scoring boundary if implemented.
- Accepted limitations / tech debt: No scorer, ranking orchestration, corpus refresh/cache owner, calibrated channel weights, or public integration yet.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Do not call ts_rank_cd a BM25 implementation.
- Missing scorer files remain listed as unfinished until behavior and tests exist.
- Final ordering has a stable document_id tie-break.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. The formula is a proposed design choice, not observed execution. EXP-0004 defines the required comparison against the current baseline.

- [`backend/src/backend/search/ranking/bm25.py`](../../../backend/src/backend/search/ranking/bm25.py)
- [`backend/src/backend/search/ranking/ranking.py`](../../../backend/src/backend/search/ranking/ranking.py)
- [`backend/src/backend/search/ranking/types.py`](../../../backend/src/backend/search/ranking/types.py)
- [`backend/src/backend/search/service.py`](../../../backend/src/backend/search/service.py)

## Revisit when

- Statistics integration tests pass and a fixed query judgment set is available.

## Rules for future changes

- Record formula and normalization semantics before implementing scoring.
- Evaluate candidate recall as well as final ranking quality.
- Supersede ADR-0003 only when the public ranking behavior actually changes.
