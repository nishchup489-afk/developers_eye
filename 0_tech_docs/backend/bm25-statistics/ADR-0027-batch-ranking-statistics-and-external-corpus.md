---
id: ADR-0027
title: Batch query statistics and keep full-corpus aggregation outside the request path
status: accepted
date: '2026-11-02'
area: backend
feature: bm25-statistics
code:
- backend/src/backend/search/ranking/statistics.py
- backend/src/backend/search/ranking/types.py
supersedes: null
superseded_by: null
related:
- ADR-0028
- EXP-0003
- ADR-0038
---

# ADR-0027: Batch query statistics and keep full-corpus aggregation outside the request path

## TL;DR

Load all query-term document frequencies in one statement and candidate TF/lengths in another, per channel. Supply corpus N and average length separately; there is no automatic cache in this module.

## Context

Calling TF once per candidate-term and length once per candidate creates N+1-style round trips. Recomputing the entire corpus for each query is still expensive even if combined into one statement.

## Decision

load_channel_statistics accepts an explicit CorpusStatistics, at most 200 unique candidate IDs, 32 unique terms and 256 characters per term. DF is a UNION ALL of per-term @@ counts using plainto_tsquery and the channel configuration. Candidate TF and DL come from one lateral unnest(vector), position cardinalities and a filtered JSONB aggregate, grouped by document ID. Corpus calculation separately scans all indexed rows, including rows whose selected channel is empty. The loader validates inputs but does not establish a consistent database snapshot, schedule refreshes or normalize raw query operators.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Batched statistics over existing vectors | Two round trips per nonempty channel | DF counts and vector expansion still cost database work | chosen for current storage |
| Per-document/per-term helpers in a nested loop | Easy first implementation | Round trips grow with candidates times terms | replaced |
| Persist exact TF/DL and per-channel aggregates now | Lower request work | New schema, deletion and rebuild obligations | planned next optimization |

## Why

Batching removes avoidable client/server latency while preserving current storage. It must not be confused with constant database work or exact BM25 statistics.

## Consequences

- Gained: No per-candidate round trip in the batch API; immutable validated statistics contracts.
- Accepted limitations / tech debt: Stored positions approximate TF/DL, ignore field weights in these counts, and may truncate. Re-parsing an already-normalized term for DF while matching TF by exact lexeme needs consistency tests. A stale corpus snapshot can violate DF<=N validation.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Corpus aggregation is not called inside load_channel_statistics.
- DF, TF, DL and corpus use the same channel definition.
- One AsyncSession is not used concurrently across channel tasks.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Replaced [581d7b2](https://github.com/nishchup489-afk/developers_eye/commit/581d7b29befeabb3ee95f43889c84d320bdd1390) with [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). [PostgreSQL 16 limits](https://www.postgresql.org/docs/16/textsearch-limitations.html) cap positions at 16,383 and 256 positions per lexeme, so stored positions are not exact original token counts. EXP-0003 records round-trip analysis, not latency.

- [`backend/src/backend/search/ranking/statistics.py`](../../../backend/src/backend/search/ranking/statistics.py)
- [`backend/src/backend/search/ranking/types.py`](../../../backend/src/backend/search/ranking/types.py)

## Revisit when

- Before connecting these statistics to ranking on the public route.
- DF count/expansion cost dominates measured request latency.
- A corpus refresh produces inconsistent counts or becomes too expensive.

## Rules for future changes

- Require PostgreSQL fixtures for stemming, empty/stripped vectors, long documents and concurrent updates.
- Do not use combined search_terms counts as per-channel BM25 DF.
- Persist exact stats only with transactional update/delete/rebuild semantics.
