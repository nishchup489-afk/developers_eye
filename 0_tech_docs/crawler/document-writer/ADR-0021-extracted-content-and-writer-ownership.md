---
id: ADR-0021
title: Persist extracted documents rather than raw HTML in the primary store
status: accepted
date: '2026-11-02'
area: crawler
feature: document-writer
code:
- crawler/src/crawler/writer
- backend/src/backend/models/documents.py
- crawler/src/crawler/worker/jobs/utility.py
supersedes: null
superseded_by: null
related:
- ADR-0011
- ADR-0002
- ADR-0019
---

# ADR-0021: Persist extracted documents rather than raw HTML in the primary store

## TL;DR

Store normalized searchable content and metadata, with the writer deciding insert/update behavior. Retain document identity when pages become unavailable; searchable index state is removed separately.

## Context

The immediate consumer is a text/code index. Keeping every raw HTTP payload would add storage and replay/versioning work that the current MVP does not implement.

## Decision

Persist canonical URL, extracted text, metadata, content hash, source linkage and freshness. Document canonical URL is globally unique, while frontier identity is per source; if two sources store that same URL, the most recently written source wins. Raw HTML is not retained. Canonical hints pass normalization/safety validation before use. Successful stores restore availability; 404/410 records unavailability and removes index/vocabulary state transactionally. noindex excludes indexed content. ADR-0011 remains the authority on soft availability.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Extracted document store | Small, directly useful index input | Cannot reparse old HTML offline | chosen |
| Store all raw responses in Postgres | Full replay source | Storage, retention and large-row costs | deferred |
| Hard-delete disappeared pages | Simple apparent cleanup | Loses identity and makes recovery harder | rejected |

## Why

Preserving extracted content supports indexing and inspection now; preserving raw payloads would require an explicit retention and replay design.

## Consequences

- Gained: Stable document identity and a clear parser/writer ownership boundary.
- Accepted limitations / tech debt: An extractor fix generally needs a recrawl; content hashes do not automatically collapse every duplicate URL. Cross-source provenance for one canonical URL is not retained as a many-to-many relation.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Parsers and processing functions do not commit documents.
- Availability changes cannot leave searchable stale rows intentionally visible.
- Metadata-only searchable changes advance the document revision.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`crawler/src/crawler/writer`](../../../crawler/src/crawler/writer)
- [`backend/src/backend/models/documents.py`](../../../backend/src/backend/models/documents.py)
- [`crawler/src/crawler/worker/jobs/utility.py`](../../../crawler/src/crawler/worker/jobs/utility.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests/crawler/writer`](../../../crawler/tests/crawler/writer)
- [`crawler/tests/crawler/worker/test_postgres_pipeline.py`](../../../crawler/tests/crawler/worker/test_postgres_pipeline.py)

## Revisit when

- Reparsing without recrawling becomes an explicit product or debugging requirement.
- Storage analysis supports a versioned object-store capture policy.

## Rules for future changes

- Do not add raw-body persistence without retention, size and replay contracts.
- Keep removal and revival semantics covered by persistence tests.
