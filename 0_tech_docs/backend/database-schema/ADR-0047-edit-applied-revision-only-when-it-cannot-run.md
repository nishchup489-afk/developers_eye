---
id: ADR-0047
title: Edit an applied revision only when it cannot run and the schema stays identical
status: accepted
date: '2026-11-08'
area: backend
feature: database-schema
code:
- backend/alembic/versions/28efc23fadfc_update_search_index.py
supersedes:
superseded_by:
related:
- ADR-0022
- INC-0034
---

# ADR-0047: Edit an applied revision only when it cannot run and the schema stays identical

## TL;DR

ADR-0022 says applied revisions stay unchanged. This adds one exception: a revision that cannot complete on some valid database may be edited, if every database that already passed it ends up with the same schema. A forward revision cannot help, because Alembic never gets past the broken one.

## Context

28efc23fadfc failed on any populated `search_index` (INC-0034). ADR-0022 rejected editing applied revisions because stamped databases never run the repair. That reasoning is right for a revision that ran and produced the wrong schema. Here the affected databases never ran it.

## Decision

An applied revision may be edited only when all of these hold:

1. It fails on a valid database state, so a later revision cannot be reached.
2. The schema it produces is unchanged, compared by column, nullability, default and index.
3. A test runs the repaired path with rows present.

Anything else, including every case where a revision ran and left the wrong schema, stays a new forward revision as ADR-0022 says.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Edit the revision under these conditions | Fixes the only place the failure can be fixed | Revision file differs from the one some databases ran | chosen |
| B. Keep the truncate workaround | No revision edit | Empties search during upgrade, manual step | rejected: ADR-0022 rules out undocumented truncation, and it hurts users |
| C. Squash the chain into a new baseline | Removes the old revision | Breaks every stamped database | rejected: far larger than the problem |

## Why

Databases already past the revision are unaffected, because the final schema is the same and Alembic does not rerun it. The edit only changes behaviour where the old version could not finish.

## Consequences

- Gained: older populated databases can reach head without losing their index.
- Accepted limitations / tech debt: the file no longer matches what ran on databases that passed it. The final schema does.
- What now depends on this decision: any future repair of a revision that cannot run.

## Invariants

- The repaired revision ends with `code_vector` NOT NULL, no default, and a GIN index.
- A populated upgrade test exists for each revision edited under this rule.

## Evidence

- Measured: `test_code_vector_upgrade_keeps_a_populated_index_and_requeues_it` failed before the edit and passes after it.
- Tests: `backend/tests/integration/test_migrations.py`.
- Commits: db53e55.

## Revisit when

- A second revision needs this exception, which would suggest checking every revision with a populated test.

## Rules for future changes

- Do not edit a revision that ran and produced a wrong schema. Add a forward revision.
- Do not change the final schema of an applied revision.
- Regression tests that must keep passing: `backend/tests/integration/test_migrations.py`.
