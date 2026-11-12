---
id: EXP-0009
title: Human-judged lexical search relevance — BM25 versus PostgreSQL
status: running         # planned | running | done
outcome: inconclusive  # adopt | reject | inconclusive
date: 2026-11-06
area: backend
feature: ranking
informs:
  - ADR-0045
  - ADR-0046
related:
  - EXP-0004
  - EXP-0007
  - ADR-0010
  - ADR-0024
  - ADR-0028
code:
  - backend/tests/unit/test_relavance_matrics/precision@10.py
  - backend/tests/unit/test_relavance_matrics/mrr@10.py
  - backend/tests/unit/test_relavance_matrics/nDCG@10.py
  - backend/tests/unit/test_relavance_matrics/recall@100.py
  - backend/tests/unit/test_relavance_matrics/relavance_runner.py
  - scripts/search_relevance_diagnostics/diagnose_relevance.py
---

# EXP-0009: Human-Judged Search Relevance Metrics

## Question

**Within the same retrieved candidate pool for a query, does Developer's Eye's custom BM25 order results more usefully than the PostgreSQL native ranking comparator?** What retrieval, ranking, or result-presentation failures do direct human judgments expose that mathematical golden tests cannot?

This experiment does **not** compare two independently retrieved web corpora, and it cannot establish general search quality from only two judged queries.

## Why it matters

EXP-0004 established reproducible BM25 mathematics and isolated a real failure for `Q051` (`javascript fetch examples`): the relevant, already indexed MDN *Using the Fetch API* document (`document_id=51`) entered the candidate set after a preliminary retrieval change but was still ranked around position 80 by custom BM25. An engine can compute BM25 correctly and still produce poor search results.

Separate these dimensions:

1. **Corpus coverage:** Is a useful document indexed at all?
2. **Candidate retrieval:** Does retrieval admit the indexed useful document to the pool?
3. **Ranking:** Does the final ranker place it near the top?
4. **Presentation:** Are language variants and near-duplicates wasting top-K positions?

Judgment labels measure *topical utility for a specified query*. Language suitability and duplicate diversity require **additional annotations or metrics**; do not quietly modify topical labels after seeing scores.

## Setup

| Item | Observed / configured |
| --- | --- |
| Developer environment | Windows PowerShell; Python 3.14.4; Poetry |
| Corpus | Developer documentation in PostgreSQL; 42,114 indexed documents reported by the earlier 100-query diagnostic in EXP-0004 |
| Primary ranker | Custom TEXT/CODE BM25 |
| Comparator | PostgreSQL native ranking as recorded in `postgresql_order`, described in EXP-0004 as `ts_rank_cd` reranking |
| Comparison control | `bm25_order` and `postgresql_order` from **one** `diagnostics.json` case must contain the same candidate IDs |
| Judging interface | Rich interactive terminal; `o` opens a document; `0`–`3` grades; `s` skips; `q` quits |
| Persistence | `backend/evaluation/exp-0009/exp0009_human_labels.csv` keyed by run ID, query ID, document ID |
| Initial judgment depth | Union of the two rankers' top 10, with optional independently known document anchors |
| Query coverage so far | Q051 and Q024 only |
| Snapshot limitation | Q051 and Q024 used **different diagnostic run IDs**; corpus immutability across runs was not established |

### Diagnostic runs and raw evidence

| Query | Query text | Run ID | Labeled documents | Evidence |
| --- | --- | --- | ---: | --- |
| Q051 | `javascript fetch examples` | `20261107T020058Z-1q` | 16 | `backend/reports/exp-0004/20261107T020058Z-1q/diagnostics.json` |
| Q024 | `FastAPI Depends` | `20261107T012318Z-100q` | 13 | `backend/reports/exp-0004/20261107T012318Z-100q/diagnostics.json` |

The timestamps above are UTC-style diagnostic identifiers; the experiment date is the developer's local date (November 6, 2026). Raw human-labeling evidence is stored in `exp0009_human_labels.csv`; result summaries are stored under `backend/reports/exp-0009/`.

## Judgment rubric

| Grade | Definition | Counts as relevant for P@10 / RR@10 / known R@100? | nDCG gain (`2^grade − 1`) |
| --- | --- | --- | ---: |
| 0 | Irrelevant to the developer's query | No | 0 |
| 1 | Tangential / related without adequately answering intent | No | 1 |
| 2 | Useful / substantially answers intent | Yes | 3 |
| 3 | Excellent / directly answers intent, ideally with actionable examples | Yes | 7 |

Judge the document itself, not its search position, ranking score, or title alone. Browser auto-translation may enable a judge to understand a foreign-language page; that does **not** mean the original page matches every user's language preference. Keep topical relevance and language suitability as separate attributes.

The runner shuffles the required judgment list deterministically and saves each answer. Existing judgments are reused for a matching diagnostic `run_id`. The current CSV and Rich runner are a **single-judge exploratory protocol**, not an inter-annotator reliability study.

## Metrics

### Precision@10

\[
P@10 = \frac{\sum_{i=1}^{10}\mathbb{1}(rel_i \ge 2)}{10}
\]

An unfilled result slot counts in the denominator; a returned but unjudged document causes an evaluation error/incomplete status rather than silently becoming grade 0.

### Reciprocal Rank@10 and Mean Reciprocal Rank@10

\[
RR@10 = \begin{cases}1/r,& r\le 10\text{ is the first rank with }rel_r\ge2\\0,&\text{otherwise}\end{cases}
\]

For one query the result is **RR@10**. **MRR@10** is the arithmetic mean across scored queries; one-query output cannot establish an overall MRR benchmark.

### Graded nDCG@10, judged-pool normalization

\[
DCG@10 = \sum_{i=1}^{10}\frac{2^{rel_i}-1}{\log_2(i+1)},\qquad nDCG@10 = \frac{DCG@10}{IDCG@10}
\]

`IDCG@10` is calculated from all *currently judged* documents for that query. Grade 1 contributes a positive gain even though it is not binary-relevant. If no judged document has a positive grade, the metric is undefined (`N/A`). Pool completeness affects nDCG; label depth and independent anchors must be recorded.

### Known-relevant Recall@100 (NOT exhaustive recall)

\[
KnownR@100 = \frac{|Top100\cap\{d:\,judged\_grade(d)\ge2\}|}{|\{d:\,judged\_grade(d)\ge2\}|}
\]

The denominator includes **only known judged relevant documents**, largely pooled from the rankers being assessed. It is biased and must **not** be presented as corpus-wide Recall@100. To measure candidate-retrieval recall, build an independent, more comprehensive per-query relevance set that can contain documents neither ranker retrieved.

### What is not yet measured

Language preference satisfaction, duplicate-group diversity, diversity-adjusted P@10, coverage of all relevant documents, robustness across query categories, test-set variance, or a controlled latency comparison.

## Method

1. Capture `diagnostics.json`, exact source/corpus configuration, query IDs, ranking parameters, and candidate budgets. Within each query, the two rankers must evaluate identical candidate ID sets.
2. Form an assessment pool from the union of both algorithms' top-K results. In Q051 include the independently tracked document `51` so a relevant page below top 10 can be labeled.
3. Human-grade the result pages 0–3; save graded labels with `run_id`, query ID and document ID. Do not auto-label from BM25 or PostgreSQL scores.
4. Run standalone metric self-tests, then score. Compare both rankers **within the same diagnostic**, never treat different runs as a controlled corpus snapshot.
5. Inspect bad cases individually. Register hypotheses, not causes, until a controlled ablation isolates a ranking feature or retrieval change.
6. Expand to a representative, versioned set of queries, ideally split into development and held-out queries. Re-run both systems on the **same frozen index snapshot** before making architecture or shipping decisions.

### Baseline versus variable

- **Controlled within a diagnostic:** query, candidate IDs, document metadata, judgment rubric.
- **Compared:** ordering of those candidate IDs by custom BM25 versus the PostgreSQL comparator.
- **Not controlled across the first two human-labeled cases:** exact index/corpus snapshot; run IDs differ.
- **Runs:** one recorded human-judgment exercise each for Q051 and Q024. This is a case study, not repeated statistical measurement.

## Reproduce

From `backend/` in PowerShell; keep your actual on-disk filename, **`relavance_runner.py`**, which differs from the corrected English spelling. The nDCG module on disk is capitalized `nDCG@10.py` in the supplied file tree; the earlier generated runner imports lowercase `ndcg@10.py`. On Windows this often resolves due to case-insensitive paths; standardize the casing before moving to Linux/CI.

```powershell
# Verify the runner + metric modules installed on your machine.
Get-ChildItem tests/unit/test_relavance_matrics/

# Run the metric self-tests (requires the runner's imports to match filenames).
poetry run python "tests/unit/test_relavance_matrics/relavance_runner.py" --self-test

# Reproduce Q051 report against its exact existing diagnostic; no prompt when already labeled.
poetry run python "tests/unit/test_relavance_matrics/relavance_runner.py" `
  --report "reports/exp-0004/20261107T020058Z-1q/diagnostics.json" `
  --query-id Q051 --include 51 --score --details

# Reproduce Q024 against its original 100-query diagnostic.
poetry run python "tests/unit/test_relavance_matrics/relavance_runner.py" `
  --report "reports/exp-0004/20261107T012318Z-100q/diagnostics.json" `
  --query-id Q024 --score --details

# Grade a NEW query only if it appears in the selected diagnostic.
poetry run python "tests/unit/test_relavance_matrics/relavance_runner.py" `
  --report "reports/exp-0004/20261107T012318Z-100q/diagnostics.json" `
  --query-id Q083 --details

# Reopen existing grades for review, if necessary.
poetry run python "tests/unit/test_relavance_matrics/relavance_runner.py" `
  --query-id Q024 --regrade --details
```

If the local runner uses lowercase `ndcg@10.py`, rename `nDCG@10.py` to `ndcg@10.py` before running Linux CI. The file tree also showed `precision@10.py`, `mrr@10.py`, `recall@100.py` and `relavance_runner.py`.

## Results

### Human relevance comparison (two query-specific snapshots)

| Query | Ranker | P@10 | RR@10 | nDCG@10 (judged pool) | Known R@100 | Judged |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Q051 · `javascript fetch examples` | BM25 | **0.000** | **0.000** | 0.034 | **1.000** | 16 |
| Q051 · `javascript fetch examples` | PostgreSQL | **0.000** | **0.000** | 0.224 | **0.000** | 16 |
| Q024 · `FastAPI Depends` | BM25 | **1.000** | **1.000** | **1.000** | **1.000** | 13 |
| Q024 · `FastAPI Depends` | PostgreSQL | **1.000** | **1.000** | **1.000** | **1.000** | 13 |

**Do not report a combined two-query macro-average as a controlled benchmark:** the underlying diagnostic/corpus snapshots differ. The values above are outputs of the developer-supplied Rich evaluation runs, not reproduced against a mounted production database here.

#### Case Q051: highly relevant result ranked too low

- MDN *Using the Fetch API*, document `51`: **human grade 3**, included in candidates; approximately **BM25 rank 80** and **PostgreSQL comparator rank 133** in the local diagnostic (see EXP-0004).
- Both rankers: **zero** grade-2/3 documents in their top ten, hence P@10 and RR@10 are zero.
- BM25 top 10: largely unrelated `Promise.any` and WebAssembly references. Of the top ten, the last page (*Making network requests with JavaScript*) was graded 1.
- PostgreSQL top 10: several grade-1 pages (*Resource timing*, *XMLHttpRequest API*, *Making network requests with JavaScript*), but no grade-2/3 page.
- Positive but low nDCG values are **not a calculation bug**: grade 1 has a positive graded gain; PostgreSQL places more grade-1 pages higher.
- Both systems' top 10 were poor on this query **despite** an already indexed relevant document. This isolates at least one final-ranking quality problem; it does **not** prove that omitted A/B/C/D weights caused the failure.

**Judgment review candidate:** *Making network requests with JavaScript* was graded 1; if page content actually contains actionable `fetch()` examples, reassess consistently using the rubric. Do not change a grade to make one ranker look better.

#### Case Q024: perfect topical scores with duplicate-language saturation

- Both systems scored 1.000 across all four reported metrics. All 13 judged documents in the Q024 pool received grade 3.
- PostgreSQL top ten included repeated translations of *Dependencies — Depends() and Security()* from FastAPI: locale-prefixed URLs such as `/tr/`, `/ru/`, `/ja/`, `/ko/` in addition to English.
- BM25 ranked distinct FastAPI dependency topics (sub-dependencies, tutorial, global dependencies) near the beginning, then several translated variants of the same reference page.
- The browser auto-translated non-English pages during human assessment. Therefore grade 3 reflects **translated topical usefulness**, not direct English-language suitability or result-list diversity.
- A top ten packed with translations can score P@10 = nDCG@10 = 1 while still having poor diversity. This is a **presentation/reranking deduplication hypothesis**, not proof of a particular canonicalization strategy.

### Report artifact paths

```text
backend/reports/exp-0009/20261107T020058Z-1q-Q051.json
backend/reports/exp-0009/20261107T020058Z-1q-Q051.md
backend/reports/exp-0009/20261107T020058Z-1q-Q051.html
backend/reports/exp-0009/20261107T012318Z-100q-Q024.json
backend/reports/exp-0009/20261107T012318Z-100q-Q024.md
backend/reports/exp-0009/20261107T012318Z-100q-Q024.html
backend/evaluation/exp-0009/exp0009_human_labels.csv
```

The paths above are from the supplied terminal logs. The documents are on the developer's local machine and have not been copied into this documentation artifact.

## Analysis

### Confirmed by the judged samples

1. **Mathematically valid ranking is not sufficient for relevance.** Q051 has no useful top-ten result under either scorer, despite a known useful candidate.
2. **Native PostgreSQL ranking is not universally better or worse on this evidence.** It assigns tangential results better positions in Q051, while Q024 is tied by all scored metrics.
3. **Topical relevance metrics alone do not measure language fit or diversity.** Q024's translations received grade 3 and inflated apparent satisfaction of a single content need.
4. **The two evaluated rankers share candidate selection.** No independent crawler-coverage or retrieval-recall comparison was performed.

### Limitations and threats to validity

- **Sample size and selection:** two handpicked queries, not representative of search traffic. No useful inference of aggregate performance or statistical significance.
- **Cross-run confounding:** Q051 and Q024 were graded from separate diagnostics; no frozen common corpus was established.
- **Incomplete relevance pool:** nDCG@10 uses judged-pool IDCG; known-relevant recall is not exhaustive recall.
- **Language assistance:** browser translation changes actual human access to locale-specific content and should be tracked explicitly.
- **Duplicate documents:** distinct doc IDs can correspond to largely equivalent translations, raising P@10 without raising result diversity.
- **Subjective judgments:** one judge, no adjudication or inter-rater agreement study. Query Q051's grade-1 documents may warrant review.
- **Internal comparator scope:** a *same-candidate-set reranking* comparison is not a comparison against a native PostgreSQL retrieval pipeline of its own.
- **Diagnostics provenance:** local logs are evidence of completed runs; no database-backed re-execution was performed for these docs.

## Outcome

**Inconclusive for an overall ranking choice; confirmed actionable failure modes. Keep EXP-0009 running.**

- Preserve custom BM25 as an evaluated baseline; **do not declare it better than PostgreSQL**.
- Track field-aware ranking and title relevance experiments under **ADR-0045 (proposed)**; test ablations against held-out judgments before adopting changes.
- Track locale-aware result grouping and language preference under **ADR-0046 (proposed)**; preserve all indexed language variants and measure diversity independently.
- Expand judgments to 10–20 representative queries **from one frozen diagnostic/corpus snapshot**, then to a larger held-out set. Include exact identifiers, tutorials, APIs, error messages, code-heavy queries, zero-result tests and locale-heavy cases.
- Record new metrics alongside existing ones: unique content groups@10, duplicate saturation@10, primary-language@10, and query-specific candidate coverage when independent anchors exist.
- Document candidate-selection changes and reranking changes separately; preserve the known target document `51` as a regression case.
- When reporting completion, distinguish **the implemented metric comparison tool** from **a statistically defensible search relevance evaluation**. The first exists; the second is not finished.

## References

- `0_tech_docs/backend/ranking/EXP-0004-lexical-relevance-evaluation.md`
- `0_tech_docs/backend/ranking/ADR-0028-candidate-bm25-ranking-plan.md`
- `0_tech_docs/backend/ranking/ADR-0045-evidence-gated-field-aware-ranking.md` (proposed)
- `0_tech_docs/backend/ranking/ADR-0046-locale-aware-result-grouping.md` (proposed)
- `backend/reports/exp-0004/20261107T020058Z-1q/diagnostics.json`
- `backend/reports/exp-0004/20261107T012318Z-100q/diagnostics.json`
- `backend/reports/exp-0009/20261107T020058Z-1q-Q051.md`
- `backend/reports/exp-0009/20261107T012318Z-100q-Q024.md`
