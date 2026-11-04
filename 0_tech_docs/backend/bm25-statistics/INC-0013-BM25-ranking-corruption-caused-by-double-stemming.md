---
id: INC-0013
title: BM25 ranking corruption caused by double-stemming
status: resolved
date: 2026-11-03
severity: high
area: backend
feature: bm25-statistics
code:
  - backend/src/backend/search/ranking/statistics.py
  - backend/src/backend/search/tokenizer.py
  - backend/src/backend/search/ranking/bm25.py
  - backend/tests/integration/test_ranking_statistics.py
  - backend/tests/unit/test_ranking.py
  - backend/tests/unit/test_ranking_orchestrator.py
fix_commits:
  - cc5e62a921f1776e52d55f937a5640bb24c9960c
related:
  - ADR-0027
  - ADR-0028
---

# INC-0013: BM25 ranking corruption caused by double-stemming

## Signature

An already-normalized English `tsvector` lexeme was normalized again when calculating document frequency (DF):

```text
Original query:      universe
Indexed/query lexeme: univers
DF lookup (before):  plainto_tsquery('english', 'univers') -> 'univ'
Correct DF lookup:   exact tsquery lexeme 'univers'

Observed live-corpus counts before the fix:
  Exact 'univers' DF:             311
  Re-stemmed 'univ' DF:            5
```

The earlier audit measured **299 versus 4** on a different corpus snapshot. The subsequent manual database check measured **311 versus 5**. These are distinct observations, not a single fixed dataset.

## Summary

Developer's Eye's BM25 statistics loader accepted lexemes that the PostgreSQL tokenizer had already normalized. However, `_get_document_frequencies()` passed each lexeme through `plainto_tsquery()` again. PostgreSQL's English stemmer can change a stemmed lexeme further, so the DF lookup could count documents for a **different term** than the TF lookup.

This could give the wrong inverse document frequency (IDF) and consequently distort BM25 scores and result ordering for affected queries. Crawling and stored `tsvector` values did not need rebuilding for this defect. The extent of affected live search rankings was not measured.

## Expected vs actual

- **Expected:** `tokenize_query()` produces `univers`; DF counts documents whose indexed text vector contains the exact lexeme `univers`, matching TF's exact-lexeme comparison.
- **Actual:** DF used `plainto_tsquery('english', 'univers')`, which resolves to `univ`; TF used `t.c.lexeme.in_(('univers',))`. The two statistics described different terms.
- **Observed evidence:** The live corpus showed an exact-lexeme count of 311 versus a re-stemmed count of 5 before remediation.

## Timeline

| Date (America/New_York) | Event |
| --- | --- |
| 2026-11-02 to 2026-11-03 | Ranking audit identified the possibility of re-stemming pre-normalized lexemes and reported 299 versus 4. |
| 2026-11-03 | Manual PostgreSQL comparison reproduced the mismatch on the then-current corpus: 311 versus 5. |
| 2026-11-03 | `_get_document_frequencies()` was changed to use an exact `TSQUERY` lexeme; PostgreSQL regression tests were added. |
| 2026-11-03 | Commit [`cc5e62a`](https://github.com/nishchup489-afk/developers_eye/commit/cc5e62a921f1776e52d55f937a5640bb24c9960c) recorded the fix and tests (commit timestamp 2026-11-04 UTC). |
| 2026-11-03 | Project owner reported **68 passed in 1.19s** for the targeted ranking test command. Incident closed at the code/regression level. |

## Root cause

The statistics API takes **already-normalized, individual index lexemes**, not raw user text. The old DF query nevertheless ran the English text-search normalization pipeline a second time:

```python
# Before: re-stemmed the lexeme, potentially changing its identity.
.where(vector.bool_op("@@")(func.plainto_tsquery(config, term)))
```

In contrast, `_get_candidate_documents()` computes per-document TF by comparing lexeme strings directly:

```python
.filter(t.c.lexeme.in_(lexemes))
```

Thus DF and TF could disagree for the same BM25 term. Because BM25 computes IDF from corpus size N and DF, an artificially small DF could over-weight the term. A higher IDF could change result ordering even when the document-matching stage was otherwise correct.

## Fixes that did not work

| Attempt | Why it did not establish a fix |
| --- | --- |
| Initial integration-test execution without `TEST_DATABASE_URL` | All eight test cases skipped; no database behavior was tested. |
| Integration-test execution with invalid PostgreSQL credentials | All eight cases errored at authentication before assertions ran. |

These were test-environment blockers, not attempted production-code remedies.

## Fix

**Committed fix:** [`cc5e62a`](https://github.com/nishchup489-afk/developers_eye/commit/cc5e62a921f1776e52d55f937a5640bb24c9960c).

In `backend/src/backend/search/ranking/statistics.py`, construct a PostgreSQL `TSQUERY` value from the exact indexed lexeme, with apostrophes and backslashes escaped, and use that value in the indexed `@@` lookup:

```python
from sqlalchemy import cast, literal
from sqlalchemy.dialects.postgresql import TSQUERY


def _exact_lexeme_query(term: str):
    """Convert an indexed lexeme into a TSQUERY without stemming."""
    escaped = term.replace("\\", "\\\\").replace("'", "''")
    return cast(literal(f"'{escaped}'"), TSQUERY)

# Inside _get_document_frequencies(), replacing plainto_tsquery():
.where(vector.bool_op("@@")(_exact_lexeme_query(term)))
```

The existing `_validate_terms()` still validates individual lexemes, and the bound SQLAlchemy `literal()` value avoids constructing unparameterized SQL. The TEXT and CODE modes continue to choose their respective stored vectors. No index schema migration or index rebuild was required for the normalization fix.

## Verification

**Targeted tests reported by the project owner:**

```powershell
poetry run pytest tests/unit/test_ranking.py tests/unit/test_ranking_orchestrator.py tests/integration/test_ranking_statistics.py -v -rs
```

```text
68 passed in 1.19s
```

The committed integration suite uses a deterministic, temporary PostgreSQL `search_index` table and checks:

- `universe` tokenizes to `univers` for TEXT, whereas CODE preserves `universe`.
- Exact DF of `univers` is **2** in the six-document fixture; the old re-stemming path returns **1**.
- Independent TEXT/CODE DF, approximate TF/DL, corpus N/avgDL, IDF and BM25 scores.
- Missing terms, empty vectors, and lexemes containing apostrophes or backslashes.
- Separate unit tests check formula behavior, multi-term scoring, TEXT/CODE/ALL orchestration and stable ordering.

**Verification boundary:** 68 passing tests were reported locally; no GitHub Actions pytest run or post-fix measurement of the live corpus's 311/5 discrepancy was independently observed. The deterministic regression evidence supports closing **this specific defect**; it does not constitute a complete search-relevance or concurrency audit.

## Resolution

**Status: resolved (code defect and regression coverage).**

`_get_document_frequencies()` now looks up the lexeme the tokenizer actually supplied, aligning DF with the indexed lexeme identity used for TF. The change is committed, and the project owner reported passing targeted tests. The incident does not require a new ADR because the implementation was corrected to uphold the existing same-channel-statistics invariant in ADR-0027.

## Prevention

- **Regression tests:** Keep `test_ranking_statistics.py` in the PostgreSQL test suite, especially the `univers` versus `univ` case and exact-lexeme escaping cases.
- **CI:** Run ranking unit tests and PostgreSQL integration tests in CI against a dedicated test database; only secret-scanning CI was observed for the fix commit.
- **Documentation:** Update ADR-0027's outdated description of DF using `plainto_tsquery()` and link this incident in the BM25 statistics overview.
- **Monitoring:** No live alert for DF/TF disagreement was verified; add diagnostics if ranking drift occurs.
- **Remaining risk:** Cached N/avgDL with live DF is not transactionally snapshot-consistent during concurrent indexing. Position-derived TF/DL is approximate. Identifier-heavy query quality, native-ranking comparisons, and full golden relevance suites remain separate work.

## Rules for future changes

- Never pass an already-normalized indexed lexeme through `plainto_tsquery()` or `websearch_to_tsquery()` again in a DF lookup.
- Normalize **raw queries** using the same PostgreSQL configuration as the indexed channel; preserve extracted lexemes for statistics.
- Keep DF, TF and document lengths channel-specific: TEXT uses `search_vector`, CODE uses `code_vector`; ALL combines independently computed channel scores.
- Add a PostgreSQL regression whenever tokenization, tsquery construction or indexed-vector semantics change.
- Keep full-corpus N/avgDL calculations off the hot search path; define snapshot and refresh consistency separately.
