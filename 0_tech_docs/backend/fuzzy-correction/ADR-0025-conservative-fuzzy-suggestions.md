---
id: ADR-0025
title: Suggest bounded spelling corrections without silently rewriting developer queries
status: proposed
date: '2026-11-02'
area: backend
feature: fuzzy-correction
code:
- backend/src/backend/search/retrieval/fuzzy/candidates.py
- backend/src/backend/search/retrieval/fuzzy/correction.py
- backend/src/backend/schema/search_term.py
- backend/src/backend/models/search_terms.py
supersedes: null
superseded_by: null
related:
- ADR-0002
- INC-0007
- INC-0008
---

# ADR-0025: Suggest bounded spelling corrections without silently rewriting developer queries

## TL;DR

Use vocabulary-backed suggestions for eligible prose words while preserving technical syntax and the original query. The current fuzzy module is incomplete and cannot import; this remains a proposed end-to-end decision.

## Context

Small spelling errors should be recoverable, but rewriting API names, quoted phrases or symbols can change the question. The stored vocabulary mixes English stems and simple-config lexemes, so it is not a human spelling dictionary.

## Decision

The correction component limits queries to 256 characters and 12 tokens; eligible bare alphabetic words are 4–32 characters. Preserve quotes, operators, dotted names, URLs and likely camelCase. Check exact terms first, then intended trigram candidates (limit 20), then optimal-string-alignment edit distance (1 for words of length <=6; otherwise 2). Tie-break by distance, similarity, document frequency, term. The missing find_fuzzy_candidates and incorrect import must be repaired before use (INC-0008). Original-query-first fallback is planned; no fallback router is connected.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Conservative suggestions after exact lookup | Protects technical intent | Lower correction coverage | proposed |
| Always rewrite to nearest vocabulary word | More apparent matches | Silently corrupts symbols and phrases | rejected |
| Fuzzy match every document body | No vocabulary lifecycle | Much larger online search space | rejected |

## Why

The query service should decide when to try a suggestion and should retain provenance. Frequency helps tie-breaking but is not a relevance or correctness guarantee.

## Consequences

- Gained: A bounded correction policy whose decisions can be displayed and tested.
- Accepted limitations / tech debt: Broken imports, missing trigram candidate implementation, vocabulary overcount, and stem/surface-form mismatch block a reliable feature.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Original query remains available.
- Online correction never maintains vocabulary counts.
- Quoted or technical tokens are not silently altered.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Partial implementation and unresolved import wiring are verified statically, not by a successful live fuzzy search.

- [`backend/src/backend/search/retrieval/fuzzy/candidates.py`](../../../backend/src/backend/search/retrieval/fuzzy/candidates.py)
- [`backend/src/backend/search/retrieval/fuzzy/correction.py`](../../../backend/src/backend/search/retrieval/fuzzy/correction.py)
- [`backend/src/backend/schema/search_term.py`](../../../backend/src/backend/schema/search_term.py)
- [`backend/src/backend/models/search_terms.py`](../../../backend/src/backend/models/search_terms.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`backend/src/backend/tests/integration/test_fuzzy.py`](../../../backend/src/backend/tests/integration/test_fuzzy.py)

## Revisit when

- After import repair and vocabulary recount, evaluate correction precision on a fixed labeled set.

## Rules for future changes

- Keep fuzzy fallback disabled until imports, candidate SQL and regression tests pass.
- Do not present indexed stems as guaranteed human-friendly suggestions.
