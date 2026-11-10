# Optimization and scaling plan

Area: infra · Status: planned

## Purpose

Captures future targets with prerequisites, measurements and acceptance gates. Current correctness and integration come before cache, broker, sharding or deployment changes.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search`](../../../backend/src/backend/search)
- [`crawler/src/indexer`](../../../crawler/src/indexer)
- [`crawler/src/crawler/policy_and_politeness`](../../../crawler/src/crawler/policy_and_politeness)

## How-it-works docs

The linked source contracts and tests are the current mechanics reference; no separate mechanics guide is claimed.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0038](ADR-0038-measure-before-adding-search-infrastructure.md) | decision | Optimize measured bottlenecks before adding caches, brokers or distributed workers | proposed |
| [EXP-0005](EXP-0005-search-and-ingestion-capacity-baseline.md) | experiment | Measure search latency and ingestion interference before scaling | planned |
| [EXP-0008](EXP-0008-crawl-index-search-at-2m.md) | experiment | Measure crawl, index and search capacity for a 2M document target | done |
| [EXP-0013](EXP-0013-read-only-search-stage-profiling.md) | experiment | Separate cold DF cost from retrieval expansion and page hydration | done |
| [EXP-0015](EXP-0015-linux-crawl-write-cost-and-staged-workers.md) | experiment | Measure Linux crawl write costs and stage workers before further redesign | done |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0038, EXP-0005. Do not mark them accepted solely because this overview exists.

## Rules for future changes

- Measure before and after with the same workload and report regressions.
- Define cache invalidation and failure behavior before implementing caching.
- Keep infrastructure plans distinct from shipped features.
