---
id: EXP-0007
title: Validate BM25 statistics, exact-lexeme document frequency, and developer-query scoring
status: done
outcome: adopt
date: '2026-11-03'
area: backend
feature: bm25-statistics
informs:
  - ADR-0027
  - ADR-0028
code:
  - backend/src/backend/search/tokenizer.py
  - backend/src/backend/search/ranking/statistics.py
  - backend/src/backend/search/ranking/bm25.py
  - backend/src/backend/search/ranking/orchestrator.py
  - backend/tests/unit/test_ranking.py
  - backend/tests/unit/test_ranking_orchestrator.py
  - backend/tests/integration/test_ranking_statistics.py
  - backend/tests/integration/test_ranking_developer_queries.py
related:
  - INC-0013
  - EXP-0003
  - EXP-0004
---

# EXP-0007: Validate BM25 statistics, exact-lexeme document frequency, and developer-query scoring

## Question

Does the corrected BM25 statistics/ranking pipeline calculate document frequencies for **exact, already-normalized PostgreSQL lexemes** and produce reproducible, mathematically correct scores for ordinary, multi-term, and identifier-heavy queries across TEXT, CODE, and ALL modes?

**Acceptance criteria:** (1) an indexed English lexeme is not stemmed a second time when computing DF; (2) independently computed TF, DF, DL, average DL, N, IDF, and BM25 expectations agree with the implementation on fixed fixtures; (3) edge cases do not introduce spurious scores; and (4) TEXT/CODE scoring and ALL-mode fusion behave as designed.

## Why it matters

BM25 depends on correct corpus statistics. The earlier DF query reused `plainto_tsquery('english', already_normalized_lexeme)`, reprocessing PostgreSQL output and corrupting IDF. A passing mathematical formula test alone would not detect this data-layer defect. Identifier-heavy developer searches additionally exercise the real query tokenizer and channel-specific vector configurations.

This experiment validates the correctness foundation needed before evaluating search relevance in EXP-0004. It does **not** test whether BM25 returns better documents than `ts_rank_cd()`.

## Setup

- **Environment:** Developer-reported local Windows/PowerShell project environment, Poetry-managed Python 3.14. The precise PostgreSQL server build and hardware were not captured in the test output; the repository targets PostgreSQL 16.
- **Software:** `pytest`, `pytest-asyncio`, SQLAlchemy async sessions, `asyncpg`, PostgreSQL `TSVECTOR`/`TSQUERY`, and the repository's real ranking modules.
- **Production observation:** In an audited live corpus, the user reported **299** matching documents for the correct exact lexeme versus **4** from the faulty re-stemming query. These are point-in-time counts, not stable fixtures; they can change as indexing proceeds.
- **Fixed PostgreSQL fixture A:** Six documents containing English text and simple-config code vectors, including `universe`, `univers`, `univ`, repeated terms, stop-word-only content, and empty vectors.
- **Fixed PostgreSQL fixture B:** Eighteen documents with multi-term text and developer identifiers, including deliberately repeated and single-occurrence variants.
- **Isolation:** Integration fixtures shadow `search_index` with a connection-local temporary table and require `TEST_DATABASE_URL` pointing to an isolated PostgreSQL test database. No persistent `search_index` records are modified by the fixtures.
- **Configurations:** TEXT uses PostgreSQL `english`; CODE uses `simple`. BM25 reference calculation uses `k1=1.2`, `b=0.75`. ALL-mode fixture uses `text_weight=0.3`, `code_weight=1.7`.
- **Code revision:** Exact-lexeme DF fix and integration statistics tests appear in commit [`cc5e62a`](https://github.com/nishchup489-afk/developers_eye/commit/cc5e62a921f1776e52d55f937a5640bb24c9960c). The 18-document developer-query test file was run locally; it was **not present on the inspected repository `main` tree** when this report was prepared.

## Method

- **Baseline:** The pre-fix DF lookup passed an indexed lexeme through `plainto_tsquery('english', term)` a second time. For example, `universe` normalizes to `univers`, which can then normalize again to `univ`.
- **Variable changed:** Query DF by the **exact indexed lexeme** using a safely quoted `TSQUERY`, without invoking language stemming again; retain TEXT/CODE-specific vector selection.
- **Reference:** For known `N`, `df`, `tf`, `dl`, and `avgdl`, calculate BM25 independently of production `bm25.py`:

  ```text
  IDF = ln(1 + (N - df + 0.5) / (df + 0.5))
  BM25(term, document) = IDF * [tf * (k1 + 1)] /
      [tf + k1 * (1 - b + b * dl / avgdl)]
  Document score = sum of unique positive query-lexeme contributions
  ```

- **Checks:**
  1. Verify exact English and simple lexemes and compare DF against fixed corpus counts.
  2. Compare document TF and DL from stored `TSVECTOR` positions with known fixture contents.
  3. Compare N, average DL, IDF, individual BM25 scores, and ranking order with independent reference calculations.
  4. Test absent terms, empty vectors, stop words, short versus long documents, and repeated query-term de-duplication.
  5. Test TEXT and CODE separately; verify deterministic ALL weighted fusion.
  6. Run a real PostgreSQL integration set for `python async database`, `asyncio.create_task`, `__init__`, `get_user_by_id`, `useEffect`, and `HTTP 404`.
- **Metrics:** Assertion pass/fail and local elapsed pytest time. No retrieval relevance, recall, ranking-quality, load, or latency benchmark metric was measured.
- **Runs per variant:** One user-reported successful run per supplied pytest command; repeated-run stability was not measured. The six- and eighteen-document fixtures are deterministic.

## Reproduce

From `backend/`, configure `TEST_DATABASE_URL` for an **isolated PostgreSQL test database**, then run:

```powershell
poetry run pytest tests/unit/test_ranking.py tests/unit/test_ranking_orchestrator.py tests/integration/test_ranking_statistics.py -v -rs
poetry run pytest tests/integration/test_ranking_developer_queries.py -v -rs
```

The developer-query file must exist at `backend/tests/integration/test_ranking_developer_queries.py` to execute the second command. Do not point `TEST_DATABASE_URL` at the live crawler database.

To reproduce the *semantics* of the original defect on an indexed database, inspect the terms and compare the exact TSQUERY with the former re-stemming path:

```sql
SELECT
    websearch_to_tsquery('english', 'universe') AS normalized_query,
    plainto_tsquery('english', 'univers') AS incorrect_reparsed_query;

SELECT
    (SELECT count(*)
     FROM search_index
     WHERE search_vector @@ '''univers'''::tsquery) AS exact_lexeme_df,
    (SELECT count(*)
     FROM search_index
     WHERE search_vector @@ plainto_tsquery('english', 'univers')) AS incorrectly_reparsed_df;
```

Live counts are not expected to remain `299`/`4` after subsequent crawling; the fixed-fixture assertions are the durable regression check.

## Results

### Observed test execution

| Suite | Reported result | Elapsed | Evidence scope |
| --- | --- | --- | --- |
| BM25 formula, orchestrator, and statistics regression suite | **68 passed** | **1.19 s** | User-reported local pytest output; complete raw log not archived with this report |
| Real PostgreSQL multi-term/identifier-query regression suite | **8 passed** | **1.33 s** | User-reported local pytest output; 18-document fixture |

These are two distinct command results. They are **not** claimed to be an independently reproduced CI run or a full repository test run.

### Deterministic correctness findings

| Check | Evidence | Result |
| --- | --- | --- |
| No double-stemming | Text query `universe` yields `univers`; exact DF fixture counts `univers: 2`, `univ: 1`; former reparsing counts only `1` for `univers` | Pass |
| Independently matched DF | Audited live observation: **299 correct vs 4 incorrect**; isolated fixture asserts exact known counts | Pass for tested observations |
| Channel-specific DF | English TEXT and simple CODE fixtures have different expected lexeme counts, checked separately | Pass |
| TF and DL | Six-document fixture asserts exact stored-position counts, including repeated `univers`/`run` | Pass |
| N and avgDL | Six-document fixture: TEXT `N=6`, `avgDL=9/6`; CODE `N=6`, `avgDL=5/6` | Pass |
| IDF and BM25 | Fixed-case formula tests compare with independently coded reference; end-to-end fixture scores match expected numeric values | Pass |
| Missing terms and empty vectors | Zero DF/TF, stop-word-only vectors, and empty vectors checked; zero-scoring candidates handled | Pass |
| Multi-term text | `python async database` produces `('python', 'async', 'databas')`; expected DF `6, 5, 3`; repeated-content document ranks above single-content document with matching reference scores | Pass |
| Identifier-heavy CODE | Five parameterized cases: dotted method, Python dunder, snake case, camel case, and HTTP status; repeated occurrence scores above single occurrence | Pass |
| Repeated query terms | `get_user_by_id` scored once or twice in the query produces the same ranking/scores | Pass |
| ALL-mode fusion | Real PostgreSQL-backed case verifies `0.3 * TEXT + 1.7 * CODE` and deterministic ordering | Pass |

For the 8-case developer-query suite, the eight pytest cases are **one multi-term TEXT test, five identifier parameterizations, one repeated-query test, and one ALL-mode fusion test**.

## Analysis

**Supported:** The exact-lexeme correction prevents the reproduced double-stemming DF error; regression fixtures and independent BM25 calculations demonstrate coherent TF/DF/DL/N/avgDL/IDF/scoring under the tested conditions. Multi-term and identifier-heavy inputs flow through PostgreSQL normalization, candidate retrieval, and BM25 ranking without violating the fixture expectations. The ALL channel performs the specified weighted score fusion.

**Important limits:**

- PostgreSQL `TSVECTOR` position counts can truncate and are approximate representations of original text length/frequency, particularly for long documents. The tests validate **current stored-vector semantics**, not perfect token counts from raw document bodies.
- ALL mode is a weighted combination of TEXT/CODE scores; it is not a third independent index or separate corpus statistics channel.
- Passing identifier tests demonstrates lexical scoring under PostgreSQL configurations, **not** exact identifier preservation, AST understanding, or an explicit exact-match relevance boost.
- The live index may grow between computing cached N/avgDL and reading DF. Concurrent index modification, stale snapshots, and `DF > N` remain **unresolved** and were not stressed in this experiment.
- Passing scoring tests does not establish relevance quality, superiority over `ts_rank_cd()`, nDCG, MRR, Precision/Recall, or production latency. Those belong to EXP-0004 and subsequent search-relevance evaluations.
- The live-corpus DF observation is time-specific; the original database transcript and full CI artifact are not attached to this report.

## Outcome

**Adopt:** Retain exact-lexeme `TSQUERY` DF lookups and the verified unit/integration regressions as required protections against INC-0013. The five checklist items covered by this report are complete **within the tested scope**.

**Follow-up:**

1. Check in and run the 18-document developer-query test suite in PostgreSQL-backed CI, rather than relying only on the local run.
2. Investigate corpus-statistics freshness and consistency under concurrent indexing (`N`, `avgDL`, live `DF`, and `DF > N`) as a separate correctness issue.
3. Use EXP-0004 for BM25-vs-`ts_rank_cd()` ordering, manually judged relevance (nDCG/Precision/MRR/Recall), language/duplicate effects, and latency.
4. Maintain the fixed fixtures as regression tests whenever tokenization, index-vector construction, or scoring changes.
