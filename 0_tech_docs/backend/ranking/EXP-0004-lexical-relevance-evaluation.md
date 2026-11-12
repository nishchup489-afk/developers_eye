---
id: EXP-0004
title: Lexical retrieval, BM25 diagnostics, and golden ranking verification
status: done                 # planned | running | done
outcome: inconclusive       # adopt | reject | inconclusive
date: 2026-11-06
area: backend
feature: ranking
informs:
  - ADR-0028
  - ADR-0038
  - ADR-0045            # proposed future ranking decision; not accepted
related:
  - ADR-0010
  - ADR-0024
  - EXP-0009            # planned human-judged relevance evaluation
code:
  - backend/src/backend/search/retrieval/fts.py
  - backend/src/backend/search/retrieval/code.py
  - backend/src/backend/search/ranking/bm25.py
  - backend/src/backend/search/ranking/statistics.py
  - backend/src/backend/search/ranking/orchestrator.py
  - backend/src/backend/search/tokenizer.py
  - scripts/search_relevance_diagnostics/diagnose_relevance.py
  - backend/tests/golden/test_bm25_golden.py
---

# EXP-0004: Lexical Retrieval and BM25 Ranking Diagnostics

## Question

**Can Developer's Eye reliably retrieve candidate documents and calculate deterministic, mathematically correct BM25 rankings on fixed inputs? What failure modes remain before human-judged relevance evaluation?**

This experiment is **not** intended to establish whether BM25 is more relevant than PostgreSQL's native ranking. That requires human relevance judgments and is deferred to **EXP-0009**.

## Why it matters

The online search pipeline has two distinct ranking boundaries:

```text
Query
  -> PostgreSQL TEXT/CODE full-text candidate retrieval
  -> Merge and deduplicate candidates
  -> Load corpus and document statistics
  -> Custom TEXT/CODE BM25
  -> Weighted channel fusion (ALL mode)
  -> Deterministic final ordering
```

A relevant page excluded from the candidate set cannot be recovered by BM25. Conversely, a document may enter the candidate set and still be badly ordered by a mathematically correct scorer. We need to distinguish **candidate coverage**, **ranking correctness**, and **human relevance**.

## Setup

- **Client environment:** Windows PowerShell; Python 3.14.4; Poetry and pytest.
- **Database:** PostgreSQL; exact server version and machine specifications not recorded.
- **Production corpus:** live developer-documentation index, including Python, FastAPI, Django, MDN, and other sources.
- **Text channel:** PostgreSQL `english` `tsvector` with stemming and A/B/C/D field weights.
- **Code channel:** PostgreSQL `simple` `tsvector`, keeping technical identifiers more faithfully.
- **Final scorer:** custom BM25, default `k1=1.2`, `b=0.75`.
- **Candidate budgets:** up to 100 retrieved per channel; at most 200 unique merged candidates.
- **Golden tests:** separate, isolated PostgreSQL test database with temporary search tables, plus deterministic fixtures. **Never run these tests against the crawler's live database.**

### Captured production corpus snapshot

From `backend/reports/exp-0004/20261107T012318Z-100q/diagnostics.md`:

| Statistic | Value |
| --- | ---: |
| Indexed documents (`N`) | 42,114 |
| TEXT average indexed document length | 697.5938412665881 |
| CODE average indexed document length | 231.70477841049765 |
| Diagnostic queries | 100 |
| Diagnostic execution errors | 0 |

Corpus statistics describe this run only. The crawler can change the indexed population between later runs.

## Method

### A. Fixed 100-query diagnostics

Executed a stratified set of 100 developer queries across natural-language documentation, identifiers, code, web APIs, query operators, and edge cases. The diagnostic recorded:

- TEXT/CODE/ALL candidate counts and selected titles.
- Custom BM25 and PostgreSQL `ts_rank_cd` ordering **over the same returned candidate IDs**.
- Top-10 overlap as a *ranking-agreement diagnostic*, not as a relevance score.
- Query latency and heuristic flags such as `LOW_AGREEMENT`, `MULTILINGUAL_TOP`, and `TARGET_NOT_IN_CANDIDATES`.

Title hints are **not ground-truth relevance labels**. They can miss relevant pages whose names differ from the hint.

### B. Q051 retrieval investigation

Query: `javascript fetch examples` (`ALL` mode).

Tracked MDN document **#51**, *Using the Fetch API*, through index presence, PostgreSQL matching, candidate selection, and final BM25 ordering.

Initially confirmed that document #51:

- Exists, is available, and is indexed.
- Matches the TEXT full-text query; it does not match the CODE full query.
- Contains the relevant indexed query lexemes.
- Is included in the larger TEXT matching set, so missing crawl/index data was not the cause.

An independent SQL experiment found 489 matching TEXT documents. Under original `ts_rank_cd`, document #51 ranked **#282** among matches, outside the TEXT top-100 cutoff. Under weighted `ts_rank` with logarithmic length normalization, it ranked **#12**.

The tested PostgreSQL weight array, in **D,C,B,A order**, was:

```sql
ARRAY[0.05, 0.10, 0.35, 1.0]::real[]
```

The rank normalization argument was `1` (logarithmic document-length normalization).

A first application attempt failed because SQLAlchemy supplied `double precision[]`, whereas PostgreSQL requires `real[]` for `ts_rank(real[], tsvector, tsquery, integer)`. Explicitly casting the array to `real[]` resolved that runtime error in the subsequent local diagnostic.

The SQL weight values govern **preliminary PostgreSQL candidate selection**; they are **not** weights used by the custom BM25 scorer.

### C. Golden ranking tests

Created and ran a deterministic golden ranking suite on a separate test database. It exercises the real PostgreSQL statistics and retrieval code with a fixed corpus, expected mathematical scores, and known ordering.

The completed eight-test run covered:

1. Corpus statistics: `N`, `avgDL`, `DF`, `TF`, `DL`.
2. Exact TEXT BM25 scores and ordering.
3. The current scorer's lack of A/B/C/D field-weight sensitivity.
4. CODE identifier matching and empty-result behavior.
5. Boolean `OR`, exclusion, and phrase retrieval.
6. Exact TEXT/CODE score fusion in `ALL` mode.
7. Weighted `ts_rank` top-100 selection with 120 competing documents.
8. Insert, update, and delete mutations with updated statistics and ordering.

An earlier smaller golden test run passed **4 tests**. The final PostgreSQL-backed run reported **8 passed in 0.80 s**. These are separate execution reports; the current repository's unique test count was not independently verified.

## Reproduce

From `backend/` in PowerShell:

```powershell
# Q051 diagnostic against the configured development corpus.
poetry run python scripts/search_relevance_diagnostics/diagnose_relevance.py --id Q051 --details

# Golden tests require TEST_DATABASE_URL pointing to a dedicated,
# isolated PostgreSQL test database. Do not use the live crawler DB.
poetry run pytest tests/golden/test_bm25_golden.py -v -rs

# Existing integration coverage, also using an isolated test DB.
poetry run pytest tests/integration/test_ranking_statistics.py tests/integration/test_ranking_developer_queries.py tests/integration/test_corpus_mutation_search.py -v -rs
```

Keep diagnostic artifacts and the retrieval/scoring configuration with every comparison. For meaningful before/after quality claims, preserve the indexed corpus and candidate budgets, rather than comparing unrelated growing-corpus snapshots.

## Results

### 1. Baseline: 100-query diagnostic

| Observed diagnostic | Result |
| --- | ---: |
| Mean BM25 vs PostgreSQL top-10 overlap | ~46% |
| `MULTILINGUAL_TOP` | 56 queries |
| `LOW_AGREEMENT` | 24 queries |
| `TARGET_BELOW_K` | 9 queries |
| `TARGET_NOT_IN_CANDIDATES` | 6 queries |
| Unexpected `ZERO_RESULTS` | 4 queries |
| `THIN_POOL` | 2 queries |
| Median diagnostic query elapsed time | ~70 ms |

Flag counts overlap; do not sum them as unique problem queries. The overlap and elapsed-time values describe a diagnostic workload and are not an independently benchmarked production latency SLO.

**Raw report:** `backend/reports/exp-0004/20261107T012318Z-100q/diagnostics.md` (with matching JSON and HTML in the same directory).

### 2. Q051: candidate recovery succeeded; final relevance remains poor

| Observation | Before candidate-scoring change | After local change |
| --- | --- | --- |
| Target document | MDN *Using the Fetch API*, id `51` | Same |
| Target's preliminary TEXT ranking | `ts_rank_cd`: **#282** (SQL experiment) | Weighted `ts_rank`: **#12** (SQL experiment) |
| Target in returned merged candidates | No | **Yes** |
| Merged candidate count for Q051 | 162 | **141** |
| Target final BM25 rank | Not ranked | **#80** |
| Target `ts_rank_cd` comparison rank within diagnostic candidate set | Not applicable | **#133** |
| Diagnostic flags | `LOW_AGREEMENT`, `TARGET_NOT_IN_CANDIDATES` | `TARGET_BELOW_K` |

The target's **#12** is a preliminary TEXT-selection rank from SQL; **#80** is its final BM25 rank. The **#133** PostgreSQL comparison position is a separate `ts_rank_cd` reranking of the diagnostic candidate set. They measure different things and should not be presented as competing scores from the same stage.

The post-change final top 10 still contained mostly Promise/WebAssembly-related pages; *Using the Fetch API* appeared at #80. This is evidence of a **ranking-quality problem**, not a failure of the BM25 formula's arithmetic.

**Local diagnostic:** `backend/reports/exp-0004/20261107T020058Z-1q/diagnostics.json` (reported in the local run; may not yet be committed to the repository).

### 3. Golden verification

| Run | Reported result | Interpretation |
| --- | --- | --- |
| Initial mathematical golden tests | 4 passed | Fixed scores, ordering, orchestration, ties |
| Full PostgreSQL-backed golden suite | **8 passed in 0.80 s** | Fixed corpus, statistics, query semantics, channel fusion, candidate selection, mutations |

These tests compare actual behavior with predefined mathematical and fixture expectations. **They do not contain human relevance judgments.** Passing them does not imply that the first result is useful to a developer.

## Analysis

### Confirmed

1. **Candidate selection can suppress relevant documents.** Q051 document #51 matched the index but was excluded at the original TEXT top-100 cutoff.
2. **Weighted preliminary retrieval improves this specific case.** The experiment moved the target from #282 to #12 and a subsequent local diagnostic included it in the merged candidate pool.
3. **The final BM25 scorer does not apply indexed A/B/C/D position weights.** `ranking/statistics.py` uses `cardinality(positions)` for term frequency, and `ranking/bm25.py` consumes those plain counts. A title occurrence and a body occurrence contribute equally to `tf` for identical other statistics.
4. **The current BM25 formula and tested orchestration behavior are reproducible.** The golden fixtures passed.
5. **BM25 vs `ts_rank_cd` agreement is not relevance.** Ranking overlap, title-hint matches, and heuristic flags cannot replace human judgments.

### Not established

- Whether weighted preliminary retrieval improves overall candidate recall across the full 100 queries; a comparable post-change 100-query run has not been recorded here.
- Whether neglecting A/B/C/D field weights is the **sole or primary cause** of Q051's poor final rank.
- Whether BM25 beats the PostgreSQL baseline on Precision@10, Recall@100, MRR@10 or nDCG@10.
- Whether a new field-aware scorer, BM25F, language preference, deduplication, or title match boost improves general relevance or latency.
- Multi-process concurrency, millions-of-document performance, and production query p95 latency.

### Important confounders

- The crawler/index can grow while diagnostics run, changing `N`, `DF`, and candidate composition.
- The top-100 cutoff exists independently in TEXT and CODE retrieval; merged counts can exceed 100.
- Initial and updated candidate scoring formulas are different; the PostgreSQL diagnostic comparator may still use `ts_rank_cd`.
- Multilingual near-duplicates can dominate top-K results.
- Some title hints are too narrow. For example, a relevant page can be flagged absent because its title does not contain the expected phrase.
- Weighted `ts_rank` selection still operates over a bounded preliminary matching pool; this does not prove globally optimal top-100 selection at scale.

## Outcome

**Inconclusive for search quality; successful for mathematical correctness and the Q051 retrieval defect.**

- **Retain:** the verified custom BM25 baseline and golden fixtures.
- **Keep:** the Q051 candidate-selection fix, subject to integration regression checks and whole-query-set evaluation before claiming a general improvement.
- **Do not claim:** improved human relevance, Recall@100, Precision@10, MRR@10 or nDCG@10 based on these diagnostics.
- **Defer:** changes to the BM25 scoring model until ground-truth evaluation is available.

### Follow-up: EXP-0009 — Search relevance metrics

**Planned; not completed as part of EXP-0004.**

Construct a fixed real-document evaluation corpus and versioned human-judged `qrels`. Evaluate candidate retrieval and final ranking separately using:

- **Recall@100:** proportion of judged relevant documents retrieved in the top-100 candidate pool, with corpus/pool scope documented.
- **Precision@10:** fraction of top-10 results judged relevant.
- **MRR@10:** reciprocal rank of the first relevant top-10 result, averaged across queries.
- **nDCG@10:** discounted ranking quality with graded relevance (for example, labels 0–3).

Compare the current BM25 implementation with PostgreSQL's native ranker on the **same fixed corpus, query set, candidate budget, judgment policy, and scoring conditions**. Record per-query scores, aggregate values, confidence/variance where appropriate, latency, and regression examples. Include Q051 as a tracked failure case, but do not tune exclusively for it.

### Follow-up: ADR-0045 — Future ranking design decision

**Proposed ADR identifier only; no implementation or acceptance claimed.**

After EXP-0009, evaluate candidate approaches and record one architecture decision covering any adopted changes:

- Field-aware term-frequency scoring or BM25F with explicit field normalization.
- Title/heading/description boosts and calibrated TEXT/CODE fusion.
- Language-aware result preference and near-duplicate suppression.
- Candidate cutoff/selection policy and whether the PostgreSQL preliminary ranker should change.
- Index format, statistics storage, migration/reindex requirements, performance trade-offs, and fallback behavior.

No new scoring model is selected by EXP-0004. ADR-0045 must justify its decision with judged relevance improvements, latency measurements, and regression-test evidence.

## Evidence and references

- `backend/reports/exp-0004/20261107T012318Z-100q/diagnostics.md`
- `backend/reports/exp-0004/20261107T020058Z-1q/diagnostics.json` (local artifact reported by the developer)
- `backend/tests/golden/test_bm25_golden.py` (local golden suite; verify committed contents before linking from CI)
- `0_tech_docs/indexer/search-vectors/ADR-0010-two-weighted-tsvectors-in-postgres.md`
- `0_tech_docs/backend/ranking/ADR-0028-candidate-bm25-ranking-plan.md`
- `0_tech_docs/backend/retrieval/ADR-0024-bounded-postgres-candidate-retrieval.md`

## Revisit when

EXP-0009 produces versioned human relevance labels and baseline metrics, or a correctness regression demonstrates that candidate retrieval or BM25 violates its frozen fixtures.
