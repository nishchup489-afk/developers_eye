---
id: ADR-0022
title: Use reviewed Alembic revisions as the schema authority
status: accepted
date: '2026-11-02'
area: backend
feature: database-schema
code:
- backend/alembic/env.py
- backend/alembic/versions
- backend/src/backend/models/__init__.py
- backend/src/backend/models/search_terms.py
supersedes: null
superseded_by: null
related:
- INC-0001
- ADR-0009
---

# ADR-0022: Use reviewed Alembic revisions as the schema authority

## TL;DR

Schema changes are explicit reviewed Alembic revisions. Repair already-stamped installations with forward migrations rather than rewriting history or trusting autogeneration alone.

## Context

Empty vocabulary revisions and the nonempty-table code_vector transition show that model declarations and migration names do not prove installed schema correctness.

## Decision

Models must be visible to Alembic metadata before autogeneration. Inspect generated upgrade/downgrade SQL, constraints, extensions and indexes. 9a71c3fb20d4 repairs search_terms and pg_trgm after empty earlier revisions. The vocabulary_document_state model remains a legacy prototype artifact; its named migration is empty and there is no active writer. schema.sql is only a snapshot. Applying migrations and rebuilding derived data are separate operations.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Forward migrations plus installed-schema checks | Works with existing deployment history | Requires migration tests | chosen |
| Edit already-applied migration files | Short diff | Stamped databases never execute the repair | rejected |
| Treat ORM metadata as deployed truth | Convenient | Misses absent tables/extensions/indexes | rejected |

## Why

A reliable upgrade path must work for an existing populated database as well as a new one. Names and revision stamps alone are insufficient evidence.

## Consequences

- Gained: Reproducible repair and an auditable schema history.
- Accepted limitations / tech debt: The populated-table code_vector migration risk and INC-0001 metadata registration gaps are not fixed by this documentation PR.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- New schema behavior has an executable revision.
- Already-applied revisions remain unchanged.
- Both clean-install and upgrade paths are validated with PostgreSQL.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`backend/alembic/env.py`](../../../backend/alembic/env.py)
- [`backend/alembic/versions`](../../../backend/alembic/versions)
- [`backend/src/backend/models/__init__.py`](../../../backend/src/backend/models/__init__.py)
- [`backend/src/backend/models/search_terms.py`](../../../backend/src/backend/models/search_terms.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests/crawler/worker/test_postgres_pipeline.py`](../../../crawler/tests/crawler/worker/test_postgres_pipeline.py)
- [`crawler/tests/indexer/test_pipeline.py`](../../../crawler/tests/indexer/test_pipeline.py)

## Revisit when

- Any column becomes non-null on a populated table.
- A model or PostgreSQL extension is added or renamed.

## Rules for future changes

- Review generated migrations before applying them.
- Do not drop/truncate live derived data as an undocumented migration workaround.
