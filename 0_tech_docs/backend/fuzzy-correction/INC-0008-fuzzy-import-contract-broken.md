---
id: INC-0008
title: Fuzzy correction imports missing and self-referenced symbols
status: open
date: '2026-11-02'
severity: medium
area: backend
feature: fuzzy-correction
code:
- backend/src/backend/search/retrieval/fuzzy/candidates.py
- backend/src/backend/search/retrieval/fuzzy/correction.py
- backend/src/backend/tests/integration/test_fuzzy.py
fix_commits: []
related:
- ADR-0025
---

# INC-0008: Fuzzy correction imports missing and self-referenced symbols

## Signature

`correction.py` imports `find_fuzzy_candidates` from `candidates.py`, where that symbol is absent, and imports `get_exact_term` from `correction.py` itself.

## Summary

The intended fuzzy correction component cannot be imported in its current form. It is not invoked by the current public search service, so the existing FTS path is a separate concern.

## Expected vs actual

- Expected: Candidate lookup and exact-term lookup have concrete implementations in the modules imported by the correction service.
- Actual: candidates.py contains normalize_term/get_exact_term/upsert_term_frequencies; it has no trigram candidate search. The second import points back at the partially initialized correction module.

## Root cause

Module responsibilities and imports became inconsistent during the retrieval restructuring. pg_trgm schema/index declarations do not supply the missing Python candidate function.

## Fixes that did not work

No additional failed repair attempt is established by the cited evidence. Do not infer one from the desired outcome.

## Resolution

**Open.** Restore an explicit exact-lookup/candidate-search contract, implement bounded candidate SQL and repair imports before connecting fallback routing. Renaming a module alone will not implement the missing query.

## Prevention

- Regression test: import all public search components before running database tests.
- Database test: execute exact lookup and bounded trigram candidates with pg_trgm installed.
- Contract test: preserve original queries and technical tokens through correction.

## Rules for future changes

- Do not claim fuzzy search is working because its tests or vocabulary table exist.
- Keep the fallback path unconnected until import and PostgreSQL checks pass.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. The pre-existing search-api overview also records this wiring problem.

- [`backend/src/backend/search/retrieval/fuzzy/candidates.py`](../../../backend/src/backend/search/retrieval/fuzzy/candidates.py)
- [`backend/src/backend/search/retrieval/fuzzy/correction.py`](../../../backend/src/backend/search/retrieval/fuzzy/correction.py)
- [`backend/src/backend/tests/integration/test_fuzzy.py`](../../../backend/src/backend/tests/integration/test_fuzzy.py)
