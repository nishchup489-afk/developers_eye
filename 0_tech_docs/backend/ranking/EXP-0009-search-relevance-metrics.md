---
id: EXP-0009
title: Human-Judged Search Relevance Evaluation
status: running
outcome: inconclusive
date: 2026-11-06
area: backend
feature: ranking
informs:
  - ADR-0045
related:
  - EXP-0004
  - ADR-0028
  - ADR-0010
code:
  - backend/scripts/search_relevance_metrics/evaluate_relevance.py
  - backend/tests/unit/test_relevance_metrics.py
  - backend/scripts/search_relevance_diagnostics/diagnose_relevance.py
---

# EXP-0009: Human-Judged Search Relevance Evaluation

## Question

On the *same fixed indexed corpus and same retrieved candidate set*, how do custom BM25 and PostgreSQL's native `ts_rank_cd` comparator differ in human-judged search result quality?

Can we establish a defensible baseline for future ranking/candidate-retrieval decisions in ADR-0045?

## Why it matters

EXP-0004 established scoring correctness on golden fixtures, **not** human usefulness. It identified a document excluded by initial retrieval and still ranked #80 by BM25 after candidate recovery (Q051: *Using the Fetch API*). There are also multilingual duplication and title-weighting hypotheses.

The experiment must measure user-defined relevance rather than agreement between two algorithms or title-substring heuristics.

## Setup

- Corpus: pause crawler/indexer and run `diagnose_relevance.py` to freeze one diagnostic snapshot. Preserve the `diagnostics.json` and its `run_id`.
- Evaluation queries: start with Q024, Q051, Q071, Q083 and Q099, then expand across the existing 100-query suite.
- Systems: custom BM25 versus PostgreSQL `ts_rank_cd` **reranking the same candidate IDs**. This is not a comparison of independent retrieval pipelines.
- Judgment pool: union of top-20 documents from both systems per query; add independently known relevant anchors (where they exist in the diagnostic candidate set).
- Judge document content and query intent, not score/rank/title substring. The exported labeling CSV omits ranking positions and shuffles documents deterministically.

## Judgment rubric (qrels)

| Grade | Meaning | Relevant for binary metrics? |
|---|---|---|
| 0 | Irrelevant, incorrect technology or unrelated content | No |
| 1 | Tangential, mentions a term but does not answer intent | No |
| 2 | Useful, substantially addresses the developer's intent | Yes |
| 3 | Excellent, directly answers intent with actionable information/examples | Yes |

Leave unreviewed documents blank. **Never auto-grade from title matching, BM25/PG scores, or an LLM without separately documenting its role and validation.** Read pages before assigning a final grade. Record ambiguous reasoning in `notes`. Ideally have a second judge review a subset, then adjudicate disagreements.

## Metrics

- **Precision@10**: count documents with grade >= 2 in the top ten, divided by 10. Missing results count as nonrelevant.
- **MRR@10**: reciprocal rank of the first document with grade >= 2 in top ten, or zero if none.
- **nDCG@10 (pooled)**: graded gains `2^grade - 1`, discounted by `log2(rank + 1)` and normalized by ideal ordering of all *judged* documents. Undefined if no judged positive relevance.
- **Known-relevant recall@100 (pooled)**: proportion of judged documents with grade >= 2 that appear in the system's top 100. This is **not exhaustive Recall@100**, because not all relevant documents in the corpus have been found and judged. With top-20 judging it is especially optimistic and must not be presented as real Recall@100.
- **Expected zero results**: evaluated separately, not averaged into ranked-list metrics.

For defensible true Recall@100, use an independently assembled and sufficiently comprehensive set of relevant documents, including documents the current retrievers missed. Current experiment code cannot claim this yet.

## Method

1. Freeze ranking settings and corpus. Run the selected diagnostic cases again after all EXP-0004 candidate-selection changes.
2. Generate a blind CSV from the union of top-20 of both rankings. Add Q051's known document #51 if it appears among candidates.
3. Human-review and grade every document appearing in **either** algorithm's top-10. Review the remaining pooled items to strengthen nDCG. Do not substitute missing labels with zero.
4. Run the metric test suite and compute report JSON. Treat the first run as an observed baseline, not a tuning objective.
5. Broaden the judged set, split development/held-out queries before tuning, then rerun the **same judgments** against a new search configuration in a separately versioned experiment.
6. Record systematic issues (field-weight loss, candidate truncation, locale duplicates, identifier behavior) as hypotheses for ADR-0045, not proven causes until controlled comparisons.

## Reproduce (PowerShell, from `backend/`)

```powershell
poetry run pytest tests/unit/test_relevance_metrics.py -v

# Pause crawler/indexer before the run. Produces a new time-stamped report.
poetry run python scripts/search_relevance_diagnostics/diagnose_relevance.py --id Q024 --id Q051 --id Q071 --id Q083 --id Q099

$diag = (Get-ChildItem reports/exp-0004/*/diagnostics.json |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1).FullName

poetry run python scripts/search_relevance_metrics/evaluate_relevance.py prepare `
    --diagnostics "$diag" `
    --qrels evaluation/exp-0009/qrels.csv `
    --depth 20 `
    --include Q051:51

# Open qrels.csv and fill the relevance_grade column manually (0..3).
code evaluation/exp-0009/qrels.csv

poetry run python scripts/search_relevance_metrics/evaluate_relevance.py score `
    --diagnostics "$diag" `
    --qrels evaluation/exp-0009/qrels.csv `
    --output reports/exp-0009/baseline.json
```

The scorer rejects missing labels for either system's top-10. It also refuses to mix different `run_id`s or overwrite existing qrels/results. If new diagnostic runs are needed, preserve each qrels file and score JSON using a run-specific name.

## Results

**Not yet measured.** The evaluator's own unit tests passed (7 tests in a local Python environment), but no human-labeled qrels or production search quality metrics exist yet. No improvement of BM25 over PostgreSQL is claimed.

## Analysis

The fixed retrieved pool controls which documents each scorer can reorder, but prevents this comparison from measuring independent candidate-retrieval recall. Both rankers share the same candidate selection bottleneck. The judged pool is incomplete, and the initial hand-selected queries are not representative of all developer traffic. Expand judgments and query coverage before interpreting mean metrics as general search quality.

## Outcome

**Inconclusive / running.** Complete human judgments and record baseline P@10, MRR@10, and pooled nDCG@10. Defer any field-aware BM25/BM25F design or tuning decision to ADR-0045 after controlled before/after evaluation.
