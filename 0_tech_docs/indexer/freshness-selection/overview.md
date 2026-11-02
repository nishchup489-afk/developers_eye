# Freshness-derived index work

Area: indexer · Status: active

## Purpose

Selects missing, stale, old-version and removal work from durable document/index state. There is no separate index queue or lease table. Multiple workers can select the same snapshot; writer validation decides whether it may commit.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/indexer/selector.py`](../../../crawler/src/indexer/selector.py)
- [`crawler/src/indexer/service.py`](../../../crawler/src/indexer/service.py)

## How-it-works docs

- [`crawler/src/indexer/docs/selector.md`](../../../crawler/src/indexer/docs/selector.md)
- [`crawler/src/indexer/docs/service.md`](../../../crawler/src/indexer/docs/service.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0008](ADR-0008-indexer-work-derived-from-freshness-no-queue.md) | decision | Indexer finds work by comparing document and index freshness, with no queue or lease table | accepted |
| [ADR-0038](../../infra/performance-and-scaling/ADR-0038-measure-before-adding-search-infrastructure.md) | decision | Optimize measured bottlenecks before adding caches, brokers or distributed workers | proposed |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0038. Do not mark them accepted solely because this overview exists.

## Open issues

A repeatedly invalid document can be selected again every poll; durable failure backoff/quarantine is future work.

## Rules for future changes

- Every path that changes indexed `document` fields must set `updated_at` (ADR-0008).
- The selector never writes or locks (ADR-0008).
- A failing document is reselected every poll until failure backoff exists (ADR-0008, open).
- Measure before and after with the same workload and report regressions.
- Define cache invalidation and failure behavior before implementing caching.
- Keep infrastructure plans distinct from shipped features.
