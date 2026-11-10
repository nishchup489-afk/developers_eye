# Text and code candidate retrieval

Area: backend · Status: active

## Purpose

The legacy FTS helper searches both vectors, while the standalone code helper uses its own query semantics and hit type. Bounded candidate generation is implemented; adapters and modular routing are pending.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/search/retrieval/fts.py`](../../../backend/src/backend/search/retrieval/fts.py)
- [`backend/src/backend/search/retrieval/code.py`](../../../backend/src/backend/search/retrieval/code.py)

## How-it-works docs

- [`backend/tests/test_case.md`](../../../backend/tests/test_case.md)
- [`backend/tests/test_case_code.md`](../../../backend/tests/test_case_code.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0024](ADR-0024-bounded-postgres-candidate-retrieval.md) | decision | Use bounded PostgreSQL candidate retrieval before final ranking | accepted |
| [EXP-0017](EXP-0017-title-channel-and-dotted-identifier-recall.md) | experiment | Title-match channel and dotted identifiers recover recall misses | done |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Keep the title-match channel (`retrieval/titles.py`) in every mode and the dotted-identifier alternatives in the code channel; removing either reopens the recall misses in EXP-0017.

- Document whether a retriever contributes text, code or both.
- Add adapters and channel-contract tests before calling merge_hits.
