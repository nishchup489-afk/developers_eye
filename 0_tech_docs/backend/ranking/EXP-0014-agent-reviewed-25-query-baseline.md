---
id: EXP-0014
title: Agent-reviewed 25-query real-corpus BM25 and PostgreSQL baseline
status: done
outcome: inconclusive
date: 2026-11-09
area: backend
feature: ranking
informs: [ADR-0028, ADR-0053]
---

# EXP-0014: Judged 25-query baseline

## Question

Does the current BM25 order outperform native PostgreSQL on a fixed, graded set
of developer queries before any further ranking-weight changes?

## Why it matters

Agreement between two rankers is not relevance. The checklist needs actual
grades, source restrictions, code/error/phrase/typo/version queries, and scores
at both five and ten results.

## Setup

Windows 11, Python 3.14.4, PostgreSQL 18.3, 100,141 indexed local documents.
Capture used one repeatable-read read-only transaction and current eligibility
filters, with 100 candidates/channel. Both rankers see identical eligible IDs.
The manifest has 25 queries, including explicit Docs/GitHub source restrictions.

## Method

An editorial agent reviewed 322 pooled query/document pairs from the union of
both top-10 lists, presented alphabetically with titles and stored-content
excerpts. The qrels identify the assessor as an agent, not a human. The first
five live FastAPI Depends results had been seen during earlier UI validation;
that blinding exception is recorded. Scorer scores were not used to assign grades.

Independently selected reference URLs were checked against available indexed
documents: 22 present, three absent. Add present positives only; six additional
query/document pairs expand the pool to 328 grades. Empty typo retrieval retains
its intended positive reference and is scored as a miss. No weight tuning occurred.

## Reproduce

See the [benchmark guide](../../../backend/evaluation/checklist-25/README.md)
for exact offline scoring commands, source manifest, snapshot, qrels and results.

## Results

| Metric | BM25 @5 | PostgreSQL @5 | BM25 @10 | PostgreSQL @10 |
| --- | ---: | ---: | ---: | ---: |
| Precision | 0.776 | 0.832 | 0.736 | 0.780 |
| MRR | 0.900 | 0.920 | 0.900 | 0.9267 |
| nDCG | 0.6479 | 0.6240 | 0.7070 | 0.6885 |

Judged candidate recall: **0.9415**, equal for both scorers. One query has zero
candidates. Full-precision per-query values are retained in the result JSON.

## Analysis

BM25 has higher graded nDCG but lower precision and MRR on this set. These metrics
do not establish a universal winner. The missing Promise.all, Cache-Control and
optional-chaining reference pages are corpus-coverage gaps; weights cannot rank
absent documents. Other broad queries retrieve incidental mentions, demonstrating
why unjudged rank agreement was inadequate.

Recall is over known judged positives, not an exhaustive oracle. Grade 1 counts
as relevant under the existing contract. Sparse identifier queries can have low
P@10 because absent positions count as nonrelevant. Categories are unbalanced;
these are agent judgments, not independent human validation. The artifact freezes
rankings rather than the complete database, and content review followed capture.

## Outcome

Inconclusive for changing weights. Retain this baseline, add a human-reviewed
holdout, address corpus coverage, and rerun comparable snapshots before tuning.
The final release relevance gate is intentionally not marked complete.
