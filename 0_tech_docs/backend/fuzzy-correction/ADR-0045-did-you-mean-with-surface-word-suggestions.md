---
id: ADR-0045
title: Offer "Did you mean" on few results, with stems mapped back to real words
status: accepted
date: '2026-11-07'
area: backend
feature: fuzzy-correction
code:
- backend/src/backend/search/retrieval/fuzzy/correction.py
- backend/src/backend/search/retrieval/fuzzy/candidates.py:english_stems
- backend/src/backend/search/retrieval/fuzzy/candidates.py:find_fuzzy_candidates
- backend/src/backend/api/search.py:suggest_search_query
- frontend/app/api/search/suggest/route.ts
- frontend/lib/search.ts:shouldSuggest
- frontend/lib/search.ts:parseCorrection
- frontend/components/search-experience.tsx
supersedes: ADR-0025
superseded_by: null
related:
- ADR-0031
- ADR-0043
- INC-0008
- INC-0033
---

# ADR-0045: Offer "Did you mean" on few results, with stems mapped back to real words

## TL;DR

When a search returns fewer than 3 results, the results page asks `GET /api/search/suggest` in the background and shows "Did you mean …" if FastAPI's `GET /search/suggest` finds a correction. The user clicks to run it; `/search` never rewrites a query. Because the vocabulary stores English stems, every candidate is turned back into a readable word that PostgreSQL's `english_stem` reduces to the same stem, so users see `configuration`, not `configur`.

## Context

- `search_terms` is built by the indexer from `search_vector || code_vector` lexemes (ADR-0043). English text lexemes are Snowball stems (`configur`, `librari`, `cach`); code lexemes are unstemmed (`simple` config). It is not a spelling dictionary.
- ADR-0025 proposed conservative suggestions but nothing called them: the backend endpoint existed and was tested with mocks, the frontend had no route and no UI, and the docs listed a non-existent `/search/suggestions`.
- A relevance review (EXP-0004) found two concrete problems with the existing correction code:
  1. Distance was measured against the stem, so `configuraton` (4 edits from `configur`) got no suggestion, and when a stem did win it was shown as-is.
  2. A correctly spelled word whose surface form is not in the vocabulary (`configuration`, stored only as `configur`) looked like a typo.
- pg_trgm's default similarity threshold (0.3) misses short transpositions: `similarity('pyhton','python') = 0.27`, `similarity('libary','librari') = 0.25`.
- Developer queries carry identifiers (`AsyncSession`, `fastapi.utils`) that must never be "corrected".

## Decision

**Backend (`suggest_query_correction`)**
- Eligibility is unchanged from ADR-0025: at most 256 chars and 12 tokens; only bare alphabetic words of 4–32 letters; quoted words, mixed-case identifiers, dotted names and `and`/`or`/`not` are kept.
- A word is *known*, and left alone, if it is in `search_terms` **or** its `english_stem` lexeme is (`english_stems()` runs `ts_lexize('english_stem', word)` over `unnest(:words)`).
- Candidates: `find_fuzzy_candidates` (pg_trgm `%`, limit 20), with `pg_trgm.similarity_threshold` set to **0.2** via `set_config(..., true)`, which is local to the transaction.
- Each candidate is expanded by `surface_forms()` into itself plus stem + common Snowball suffixes (`e`, `s`, `ed`, `ing`, `ation`, `ure`, …), and `i` → `y`/`ies`/`ied`. All forms are stemmed in one query.
- A form is viable when:
  - it is the bare candidate (it may be an unstemmed code token), except a bare stem ending in `i` (`librari`, `queri`) that stems to itself; or
  - it is a derived form whose `english_stem` equals the candidate.
- Viable forms must be within OSA edit distance 1 of the **typed word** (typed word ≤ 6 letters) or 2 (longer). The winner is picked by distance, then bare-before-derived, then similarity, then document frequency, then alphabetical order.
- The response contract (`QueryCorrection`) is unchanged.

**Frontend**
- `GET /api/search/suggest` validates `q` (1–300 chars) and forwards to FastAPI with a 5 s deadline.
  - Returns `suggestion: null` without calling the backend in demo mode, for multi-line (pasted code) queries, and for queries over 256 chars.
  - A backend 422 becomes `suggestion: null`. Other upstream failures become 502, and a timeout becomes 504.
  - `parseCorrection` drops unchanged suggestions (ignoring case and whitespace) and suggestions with no corrections.
- `search-experience.tsx` only calls it after a successful search with fewer than 3 results (`shouldSuggest`), on the same `AbortController` as the search, so a newer search cancels it. Failures are ignored silently.
- The line reads "Did you mean *…*?" with corrected words in bold. Clicking runs a normal search (URL changes); the original results stay as they were.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Suggest on few results; surface forms verified by `english_stem` | Readable words; no new tables; uses the index's own stemmer | Bare stem can still win when the typo is closer to it; a few extra queries per word | chosen |
| B. Auto-rewrite `/search` to the correction | Fewer clicks | Silently changes identifiers and intent; ADR-0025 invariant | rejected: rewrites developer queries |
| C. Show stems as-is (status quo) | No extra work | `configur`, `librari` look broken to users | rejected: unreadable |
| D. Store surface forms in a second vocabulary (indexer change) | Exact original spellings, no guessing | Indexer and outbox changes, a migration, and a full recount | rejected for now: bigger change; revisit if A's misses matter |
| E. Hard-coded English dictionary | Real words guaranteed | Not in the corpus, so suggestions can return 0 results; extra dependency | rejected: drifts from the index |
| F. Always fetch suggestions with every search | Simplest UI logic | Extra DB work on every query | rejected: only useful when results are poor |

## Why

- **Correctness:** checking forms with the same `english_stem` the indexer used means any suggested word matches the indexed lexeme, so clicking it can find documents. Measuring distance to the surface form, not the stem, is what makes `configuraton` → `configuration` reachable at all.
- **Safety:** suggestions are only offered. Identifiers and quoted text keep the ADR-0025 protections.
- **Cost:** no schema or indexer change. The work runs only when results are already poor: per eligible word that is one exact lookup, one or two stem lookups, one trigram query and one batched stem query.
- **Threshold 0.2** is local to the transaction, so other trigram users (`get_fuzzy_search`, `pg_trgm.word_similarity_threshold`) are unaffected. The edit-distance gate keeps precision.

## Consequences

- Gained: a working, tested "Did you mean" path from vocabulary to UI; correctly spelled stemmed words are no longer flagged.
- Accepted limitations / tech debt:
  - A bare stem is still shown if it is the closest viable form (e.g. a typo one edit from `configur` but two from `configure`). This is rare in practice.
  - The suffix list is heuristic; irregular forms (doubled consonants: `running` → `run`) are not rebuilt.
  - The trigram query at threshold 0.2 scans more of the GIN index than 0.3. This has not been measured at 2M documents.
  - Demo mode never suggests (fixtures have no vocabulary).
- What now depends on this: the `/api/search/suggest` contract in `frontend/public/api-reference.md` and the docs page; the `suggestBelowResults` (3) and `maxSuggestQueryLength` (256) constants, which must match the backend's `MAX_QUERY_CHARS`.

## Invariants

- `/search` never applies a correction by itself; only a user click runs the suggested query.
- Every suggested word is either a bare vocabulary term or a word whose `english_stem` equals a vocabulary term.
- A bare stem ending in `i` that stems to itself is never suggested.
- A word in the vocabulary, or whose `english_stem` is, is never corrected.
- Quoted words, mixed-case identifiers and dotted names are never corrected.
- The 0.2 trigram threshold is set with `set_config(..., true)` (transaction-local), never globally.
- The frontend asks only when results < 3, the query is single-line and ≤ 256 chars; a failed suggestion never shows an error.

## Failure modes

- Vocabulary query fails: backend 503 → frontend 502 → the UI shows nothing.
- Backend hangs: 5 s deadline → 504 → nothing shown. This relies on the `abortableFetch` fix (INC-0033).
- Stale vocabulary (drainer behind, ADR-0043): suggestions trail the index by one drain cycle.

## Evidence

- Measured: `similarity('pyhton','python') = 0.27`, `similarity('libary','librari') = 0.25` (PostgreSQL 16, pg_trgm defaults).
- Tests (container run 2026-11-07, 441 backend tests passed):
  - `backend/tests/unit/test_fuzzy_suggestions.py` FS-01..09.
  - `backend/tests/integration/test_fuzzy_suggestions.py` FSI-01..04, real `english_stem`/pg_trgm: `configuraton`, `libary`, `pyhton`, `databse` → real words; `configuration`, `libraries`, `caching`, `python` unchanged.
  - Frontend: `frontend/tests/search-unit.mjs`, plus the suggestion cases in `frontend/tests/integration.mjs`.
- Assumed: the suffix list covers most stems users meet; not measured on the real vocabulary.
- Commits: `17e62be`.

## Revisit when

- The suggestion click-through or "no result after clicking" rate can be measured and shows bad suggestions.
- Trigram candidate lookup p95 exceeds 50 ms on the production vocabulary.
- Bare-stem suggestions show up in real queries often enough to notice; then consider option D.
- Autocomplete (completions while typing) is built; it is a separate contract, not this endpoint.

## Rules for future changes

- Do not make `/search` apply suggestions automatically without a new ADR.
- Do not return candidate stems without the `english_stem` round-trip check.
- Keep `maxSuggestQueryLength` in `frontend/lib/search.ts` equal to `MAX_QUERY_CHARS` in `correction.py`.
- Change the trigram threshold only transaction-locally, and re-run the integration tests.
- Regression tests that must keep passing: `backend/tests/unit/test_fuzzy_suggestions.py`, `backend/tests/integration/test_fuzzy_suggestions.py`, `backend/tests/api/test_search.py`, `npm run test:search:unit`, `npm run test:integration`.
