# BM25 ranking plan

Area: backend · Status: planned

## Purpose

The scorer and ranking orchestrator files are empty. Configuration types and statistics exist, but public results still use summed PostgreSQL ranks. The proposed formula and evaluation gates are documented before implementation.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/ranking`](../../../backend/src/backend/search/ranking)
- [`backend/src/backend/search/service.py`](../../../backend/src/backend/search/service.py)

## How-it-works docs

The linked source contracts and tests are the current mechanics reference; no separate mechanics guide is claimed.

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0028](ADR-0028-candidate-bm25-ranking-plan.md) | decision | Introduce BM25 reranking only after statistics and relevance validation | proposed |
| [EXP-0004](EXP-0004-lexical-relevance-evaluation.md) | experiment | Evaluate candidate recall and BM25 relevance against the FTS baseline | planned |

## Decisions to record

Pending implementation/evaluation choices are recorded as proposals: ADR-0028, EXP-0004. Do not mark them accepted solely because this overview exists.

## Open issues

No BM25 result ordering, corpus cache or relevance improvement is verified at the baseline.

## Rules for future changes

- Record formula and normalization semantics before implementing scoring.
- Evaluate candidate recall as well as final ranking quality.
- Supersede ADR-0003 only when the public ranking behavior actually changes.
