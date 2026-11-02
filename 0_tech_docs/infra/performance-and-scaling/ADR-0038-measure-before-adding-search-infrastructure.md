---
id: ADR-0038
title: Optimize measured bottlenecks before adding caches, brokers or distributed workers
status: proposed
date: '2026-11-02'
area: infra
feature: performance-and-scaling
code:
- backend/src/backend/search/ranking/statistics.py
- crawler/src/crawler/schedular/repository.py
- crawler/src/indexer/vocabulary.py
- crawler/src/crawler/policy_and_politeness/politeness_policy.py
supersedes: null
superseded_by: null
related:
- EXP-0001
- EXP-0004
- EXP-0005
- EXP-0006
- ADR-0027
---

# ADR-0038: Optimize measured bottlenecks before adding caches, brokers or distributed workers

## TL;DR

Prioritize correctness, a complete search path and reproducible measurements, then optimize the dominant cost. Nginx, Redis, extra processes and a separate search engine are proposed tools, not implemented scale guarantees.

## Context

The project has several potential costs: per-term DF counts, vector expansion, corpus scans, serialized vocabulary writes, host pacing, broad report queries and frontend effects. Optimizing the wrong one adds complexity without improving user latency.

## Decision

First repair vocabulary/fuzzy defects and connect the modular pipeline. Measure stage latency, SQL plans/rows/buffers, lock waits, candidate recall, index lag and resource use. Next candidates include index-time exact TF/DL/per-channel DF with transactional maintenance, scheduled versioned corpus snapshots, bounded snippet inputs and appropriate SQL indexes. Add shared politeness before overlapping crawler processes. Nginx may later terminate/proxy/cache/rate-limit HTTP; it does not optimize SQL or choose retrieval modes. Cache keys need query/mode/filter/page plus index/statistics generation and private admin bypass. No cache TTL or provider is selected here.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Measure then change one bottleneck | Attributable benefit and controlled cost | Requires baseline work | proposed sequence |
| Add Redis/Nginx for assumed speed | Familiar infrastructure | Can cache wrong/stale results and leave database work unchanged | not yet justified |
| Shard or use Kubernetes now | More deployment knobs | Distributed consistency and operations before demand | deferred |

## Why

Round-trip reduction, server execution time, useful crawl throughput and result quality are separate measurements. A target such as one million requests/second is an ambition, not an achieved result or a design assumption.

## Consequences

- Gained: A measurable decision path if adopted.
- Accepted limitations / tech debt: No production workload, SLO, hardware budget, cache policy or deployment topology has been verified for this repository.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Every performance claim states workload, hardware, cache state and correctness checks.
- Caches never turn backend failures into unlabeled demo data.
- Multiple crawlers share host limits before concurrency is raised.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Existing historical scheduler measurements remain in EXP-0001; planned studies are EXP-0004 through EXP-0006. Detailed targets and gates are in optimization-plan.md.

- [`backend/src/backend/search/ranking/statistics.py`](../../../backend/src/backend/search/ranking/statistics.py)
- [`crawler/src/crawler/schedular/repository.py`](../../../crawler/src/crawler/schedular/repository.py)
- [`crawler/src/indexer/vocabulary.py`](../../../crawler/src/indexer/vocabulary.py)
- [`crawler/src/crawler/policy_and_politeness/politeness_policy.py`](../../../crawler/src/crawler/policy_and_politeness/politeness_policy.py)

## Revisit when

- Baseline traces identify the largest cost or a correctness invariant fails.
- A second crawler process, a sustained backlog, or a measured latency target requires a new design.

## Rules for future changes

- Measure before and after with the same workload and report regressions.
- Define cache invalidation and failure behavior before implementing caching.
- Keep infrastructure plans distinct from shipped features.
