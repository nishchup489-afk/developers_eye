---
id: INC-0009
title: Code snippet boundary adjustment could exceed max_chars
status: resolved
date: '2026-11-02'
severity: medium
area: backend
feature: snippets
code:
- backend/src/backend/search/snippets/snippets.py
- backend/src/backend/search/snippets/tests/test_snippet_bounds.py
fix_commits:
- d2229b6ffb8a7f9aff270889f40ebcd115069723
related:
- ADR-0029
---

# INC-0009: Code snippet boundary adjustment could exceed max_chars

## Signature

Code-mode passage windows could exceed the caller-supplied max_chars after line-boundary adjustment.

## Summary

PR #6 added a final character-budget clamp and regression cases for code windows. This record captures the repaired code behavior; no production occurrence count or latency impact is known.

## Expected vs actual

- Expected: Every returned passage and snippet respects the hard character budget.
- Actual: Boundary handling could produce an over-budget window before the guard was added.

## Root cause

A preference for line boundaries was allowed to override the output size invariant. A formatting preference must never take priority over the hard bound.

## Fixes that did not work

No additional failed repair attempt is established by the cited evidence. Do not infer one from the desired outcome.

## Resolution

The final window computation clamps end to start+max_chars when needed. PR #6 also added regression tests and snippet mechanics documentation. The historical PR explicitly says tests were added without execution in that session.

## Prevention

- Regression test: code-mode windows around multiline matches remain within max_chars.
- Review: test both boundary preference and final output size independently.
- Remaining risk: Unicode span conversion and public integration remain separate work.

## Rules for future changes

- Apply the character-budget assertion after all boundary adjustments.
- Do not call a regression resolved in deployment merely because a test was authored.

## Evidence

Source and merged PR [#6](https://github.com/nishchup489-afk/developers_eye/pull/6); this PR does not claim a new full backend test run.

- [`backend/src/backend/search/snippets/snippets.py`](../../../backend/src/backend/search/snippets/snippets.py)
- [`backend/src/backend/search/snippets/tests/test_snippet_bounds.py`](../../../backend/src/backend/search/snippets/tests/test_snippet_bounds.py)
