---
id: ADR-0019
title: Normalize before deterministic classification and content fingerprinting
status: accepted
date: '2026-11-02'
area: crawler
feature: content-processing
code:
- crawler/src/crawler/processing/normalize
- crawler/src/crawler/processing/classifier
- crawler/src/crawler/processing/fingerprint.py
- crawler/src/crawler/processing/processing.py
supersedes: null
superseded_by: null
related:
- ADR-0009
- ADR-0021
---

# ADR-0019: Normalize before deterministic classification and content fingerprinting

## TL;DR

Process extracted content without I/O: normalize it, classify it using explicit rules, and compute a SHA-256 content fingerprint. The writer owns the persistence and deduplication decision.

## Context

Formatting noise should not create a new content revision, while code indentation and technical text must survive cleanup. A lightweight ruleset is easier to inspect than introducing ML into ingestion before search works.

## Decision

The fingerprint is domain/version separated deterministic JSON of normalized title, description, body, headings and code blocks. URL, author, publication time, tags and classification are excluded from this content digest. Classification uses source/URL/content patterns. The separate index hash includes index-relevant metadata and version: content_hash alone cannot decide whether vectors are fresh.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Deterministic rules and SHA-256 | Repeatable and dependency-light | Heuristics miss some categories | chosen |
| Hash raw HTML | Easy byte identity | Markup noise changes identity | rejected |
| ML classifier or semantic deduplication now | Potential recall across variations | Needs labels, evaluation and operational machinery | deferred |
| BLAKE3 hash | Potential speed advantage | No measured hashing bottleneck | not adopted |

## Why

Repeatable preprocessing makes recrawls and index rebuilds explainable. SHA-256 is already available and avoids adding a dependency for an unmeasured cost.

## Consequences

- Gained: Content comparison is stable across irrelevant acquisition metadata changes.
- Accepted limitations / tech debt: Exact fingerprints do not provide near-duplicate or semantic deduplication; rule-based labels are approximate.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Same normalized payload yields the same digest.
- Code formatting is not collapsed as prose.
- Changing indexed metadata still advances freshness even if content_hash is unchanged.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`crawler/src/crawler/processing/normalize`](../../../crawler/src/crawler/processing/normalize)
- [`crawler/src/crawler/processing/classifier`](../../../crawler/src/crawler/processing/classifier)
- [`crawler/src/crawler/processing/fingerprint.py`](../../../crawler/src/crawler/processing/fingerprint.py)
- [`crawler/src/crawler/processing/processing.py`](../../../crawler/src/crawler/processing/processing.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests/crawler/processing`](../../../crawler/tests/crawler/processing)
- [`crawler/tests/indexer/test_builder.py`](../../../crawler/tests/indexer/test_builder.py)

## Revisit when

- Labeled examples demonstrate unacceptable classifier error.
- Measured duplicate results justify a separate similarity stage.

## Rules for future changes

- Version changes to fingerprint semantics.
- Keep content and index hashes conceptually separate.
