---
id: ADR-XXXX
title: <decision in a few words>
status: proposed        # proposed | accepted | superseded | deprecated
date: YYYY-MM-DD
area: crawler           # crawler | indexer | backend | frontend | infra
feature: <feature folder>
code: []                # paths or path:symbol this decision governs
supersedes:             # ADR-XXXX, if any
superseded_by:
related: []             # other ADR / INC / EXP ids
---

# ADR-XXXX: <Decision title>

## TL;DR
<!-- required: two or three sentences. What we do, and the single biggest reason. -->

## Context
<!-- required -->
What problem forced a decision? What constraints existed (scale, team size, budget, deadlines, existing code)?

## Decision
<!-- required -->
What exactly we do: algorithm, data structure, library or protocol, with parameters (timeouts, limits, ordering).
Mark anything planned but not yet implemented as **planned**.

## Options considered
<!-- required: at least one rejected option -->

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. <chosen> | | | chosen |
| B. | | | rejected: <one-line reason> |
| C. | | | rejected: <one-line reason> |

## Why
<!-- required -->
Why A fits Developer's Eye better than B and C. Cover what matters here, not every heading:
correctness, performance, reliability, security, operability, cost to build.

## Consequences
<!-- required -->
- Gained:
- Accepted limitations / tech debt:
- What now depends on this decision:

## Invariants
<!-- required: things that must stay true, each one checkable -->
- 

## Failure modes
<!-- optional -->
What can go wrong and how the design handles it. Link INC records that happened for real.

## Evidence
<!-- optional, but separate measured facts from assumptions -->
- Measured:
- Assumed:
- Tests:
- Commits:

## Revisit when
<!-- required: measurable triggers -->
- e.g. more than N targets, p95 claim latency over X ms, a second worker host

## Rules for future changes
<!-- required: copy these into the feature overview.md -->
- Do not ... without a new ADR.
- Before editing, check ...
- Regression tests that must keep passing:
