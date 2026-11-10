---
id: ADR-0054
title: Retain backend as the shared schema package instead of introducing de_core
status: accepted
date: 2026-11-09
area: backend
feature: package-boundary
code: [backend/src/backend, crawler/pyproject.toml, crawler/src/crawler/worker/jobs]
supersedes:
superseded_by:
related: [ADR-0012, ADR-0013, ADR-0052]
---

# ADR-0054: Keep the current shared schema boundary

## TL;DR

Do not introduce `de_core` in this checklist pass. The backend already owns the
shared schema, contracts, and connection configuration; workers depend on it in
one direction. Clarify responsibilities and remove obsolete cross-owner imports.

## Context

A smaller shared package was proposed to reduce coupling. Splitting it now would
move SQLAlchemy model registration, Alembic imports, settings, schemas, and test
fixtures while preserving the same single PostgreSQL schema and release boundary.
There is no independently versioned third consumer requiring that migration.

## Decision

| Owner | Responsibility |
| --- | --- |
| Backend | Database models/migrations, shared contracts, query APIs, report queries, AI generation |
| Crawler | Approved acquisition, frontier/leases, network policy, parsing and document observations |
| Indexer | Freshness selection, vector writes/removals, vocabulary outbox/draining/reconciliation |
| Frontend | Interaction, same-origin proxy, admin sessions and escaped presentation |

Workers are separate processes. Crawling does not index during finalize; the
indexer observes document freshness/availability. API requests do not dispatch
crawl work. Database session and transaction ownership stay explicit.

`process_job` now delegates resource outcome planning and parsing to `resources.py`.
Finalization delegates target transition, missing/noindex handling, and document
persistence to named helpers within its single transaction. Obsolete indexer
mutation imports were removed from crawler finalization.

## Options considered

| Option | Benefit | Cost | Verdict |
| --- | --- | --- | --- |
| Keep backend as shared package | Existing install/migration boundary; small changes | Package name is broader than its shared subset | Chosen |
| Extract `de_core` now | Clearer name and narrower distribution | Large import/migration change without a third consumer or measured deployment gain | Rejected for now |
| Let each worker define its own models | Independent packages | Competing schema definitions and migration drift | Rejected |

## Why

The process boundary matters more than renaming the shared package. Existing
package-boundary tests enforce that backend never imports crawler/indexer code.

## Consequences

Backend remains a worker dependency. A future extraction should first identify
a stable settings/schema surface and an independently released consumer.

## Invariants

- Backend imports neither worker distribution.
- Crawler finalization does not mutate vectors or vocabulary.
- Refactoring helpers does not change lease fencing, atomicity, retry or policy rules.

## Evidence

Worker regressions cover all resource types, noindex, 404/410, partial sitemap
replay, deadlock retry, telemetry, and database failure recovery. Refactors are
separate commits from behavior changes.

## Revisit when

A third independently deployed consumer needs models without the API package,
or measured installation/startup cost makes a smaller distribution worthwhile.

## Rules for future changes

- Preserve dependency direction and transaction ownership.
- Split helper refactors from behavior changes and run worker/package-boundary tests.
