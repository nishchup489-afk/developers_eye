---
id: ADR-0034
title: Keep mechanics separate from decision history and generate shared navigation
status: accepted
date: '2026-11-02'
area: infra
feature: docs-navigation
code:
- scripts/update_docs_nav.py
- 0_tech_docs/_templates
- frontend/app/docs/page.tsx
- frontend/public/api-reference.md
supersedes: null
superseded_by: null
related:
- ADR-0035
---

# ADR-0034: Keep mechanics separate from decision history and generate shared navigation

## TL;DR

How-it-works documentation lives with the code; 0_tech_docs records why, alternatives, failures and revisit triggers. Generated README maps point readers to a dedicated decision index.

## Context

Future maintainers need both execution details and the reasons that should survive refactors. Rewriting a historical decision to match current code would erase the very context these docs preserve.

## Decision

Use global ADR/INC/EXP IDs and the existing templates. Accepted ADRs remain immutable unless status/supersession metadata changes through a new decision. Feature overviews are living entry points. update_docs_nav.py lists tracked Markdown and excludes agent instructions; tech docs maintain their own feature/record index. Public frontend API docs describe the caller contract and must distinguish live/demo behavior. This documentation-only capture uses code links instead of adding retrospective comments throughout runtime files; add enforcement-point references when those files next change.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Mechanics plus decision records | Explains implementation and intent | Requires coordinated updates | chosen |
| One growing README | Easy entry point | Mixes history, operations and current facts | rejected |
| Rewrite old accepted ADRs on each refactor | Always reads as current | Loses rejected options and causality | rejected |

## Why

A dated decision record is an engineering constraint with provenance, not a second copy of every function explanation.

## Consequences

- Gained: Navigable history and explicit evidence labels.
- Accepted limitations / tech debt: Older mechanics docs can be stale; source inspection wins for current behavior. Generated maps do not independently list every ADR.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Record IDs are globally unique within each type.
- Every new record appears in its feature overview and global record index.
- Proposals and unmeasured hypotheses are labeled.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Template/navigation introduction: [fc0320d](https://github.com/nishchup489-afk/developers_eye/commit/fc0320d06b8761b5194828239ff040551c37efc5).

- [`scripts/update_docs_nav.py`](../../../scripts/update_docs_nav.py)
- [`0_tech_docs/_templates`](../../../0_tech_docs/_templates)
- [`frontend/app/docs/page.tsx`](../../../frontend/app/docs/page.tsx)
- [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md)

## Revisit when

- A link/record validation fails or a source contract changes.
- The docs map generator changes its inclusion rules.

## Rules for future changes

- Do not rewrite accepted rationale to invent history.
- Update public API documentation and validators with contract changes.
- Use the generator for generated navigation blocks.
