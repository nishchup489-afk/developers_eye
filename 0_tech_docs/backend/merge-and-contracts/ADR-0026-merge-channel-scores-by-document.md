---
id: ADR-0026
title: Merge candidates by document ID while retaining independent channel evidence
status: accepted
date: '2026-11-02'
area: backend
feature: merge-and-contracts
code:
- backend/src/backend/search/merge.py
- backend/src/backend/search/types.py
supersedes: null
superseded_by: null
related:
- ADR-0024
- ADR-0028
---

# ADR-0026: Merge candidates by document ID while retaining independent channel evidence

## TL;DR

Merge by document_id, taking the maximum repeated score within each channel. Preserve text and code evidence for a later ranker; merging itself does not rank relevance.

## Context

A document can arrive through multiple retrieval paths. Adding duplicate same-channel scores would reward duplicated routing rather than document relevance.

## Decision

merge_hits consumes iterables of immutable RetrievalHit values, accumulates by ID, takes per-channel maxima, creates new hits, and sorts by document_id for deterministic output. Frozen/slotted contracts validate positive integer IDs and finite scores. RankedHit and SearchResult describe later stages; SearchResponse.total=None means the full match count is unknown. Current retriever dictionaries and CodeRetrievalHit objects are not interchangeable with these dataclasses.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| ID merge with channel maxima | Stable, avoids duplicate-route inflation | Needs adapters at boundaries | chosen |
| Sum every hit score | Simple aggregation | Duplicate hits inflate relevance | rejected |
| Pick one winning hit | Small implementation | Drops the other channel evidence | rejected |

## Why

Deduplication, evidence preservation and ranking have different purposes. Keeping them separate makes scoring changes easier to review.

## Consequences

- Gained: One candidate per document and deterministic intermediate results.
- Accepted limitations / tech debt: Document-ID deduplication does not detect equivalent content under different IDs; adapters and public-route integration remain outstanding.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Each document ID appears once.
- Inputs are not mutated.
- No final relevance ordering is claimed by merge_hits.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. Implementation commit: [f195afd](https://github.com/nishchup489-afk/developers_eye/commit/f195afd47eb37c543e52304056739a0594a70b65).

- [`backend/src/backend/search/merge.py`](../../../backend/src/backend/search/merge.py)
- [`backend/src/backend/search/types.py`](../../../backend/src/backend/search/types.py)

## Revisit when

- A new retrieval channel needs its own evidence instead of overloading text/code.
- Content duplicates measurably harm results after ID merging.

## Rules for future changes

- Add explicit retriever-to-RetrievalHit adapters.
- Preserve order independence, input immutability and duplicate-hit idempotence in tests.
