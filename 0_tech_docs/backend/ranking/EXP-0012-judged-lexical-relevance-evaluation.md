---
id: EXP-0012
title: Evaluate judged candidate recall and BM25 relevance against PostgreSQL FTS
status: running
outcome: inconclusive
date: '2026-11-06'
area: backend
feature: ranking
informs:
- ADR-0028
- ADR-0038
code:
- backend/src/backend/search/evaluation/metrics.py
- scripts/evaluate_relevance.py
- scripts/compare_rankings.py
- backend/evaluation/queries.json
- backend/tests/unit/test_relevance_metrics.py
- backend/tests/unit/test_ranking_goldens.py
---

# EXP-0012: Judged lexical relevance evaluation

Filed as EXP-0004 in PR #8. Renumbered when merged, because main already used EXP-0004 for the BM25 diagnostics record. Report folders keep the `exp-0004` name.

## Question

On a frozen, manually labeled developer-documentation corpus, does the current
custom BM25 reranker outperform PostgreSQL `ts_rank_cd` on P@10, MRR@10,
and nDCG@10, while retaining relevant documents in the bounded candidate pool?

This experiment does **not** assert that overlap or rank movement is relevance.

## Why it matters

Both scorers operate on the same already-truncated PostgreSQL candidate pool.
A ranker cannot recover relevant results that the candidate retriever omitted.
High agreement with PostgreSQL can coexist with bad user results, and low
agreement is not evidence that either scorer is better.

## Setup

- **Query manifest:** `backend/evaluation/queries.json`, 35 versioned queries
  across docs, identifiers, code syntax, mixed text/code, operators, phrases,
  typo-like inputs and no-result inputs.
- **Database:** use a snapshot ID identifying a reproducible local PostgreSQL
  database state; do not use a changing production crawl for comparison.
- **Collection:** one `REPEATABLE READ, READ ONLY` transaction for the 35 queries.
  Scan text/code corpus statistics once each and reuse for all queries.
- **Retrieval budget:** 100 per channel. `ALL` mode can return up to **200
  unique** candidates. The existing retrieval code also applies an *unordered*
  `LIMIT 20000` before provisional ranking. This is an important recall risk.
- **Baseline:** native PostgreSQL cover-density ranking on exactly the same
  candidate IDs. `ts_rank_cd(text_vector, tsquery, 0)` for text and
  `ts_rank_cd(code_vector, tsquery, 32)` for code; sum for `ALL`. The code
  normalization now matches the production code retriever.
- **Experimental ranker:** live `rank_candidates` (custom BM25) with the
  existing query tokenizer, live candidate DF/TF/DL and snapshot corpus stats.
- **Identity:** judge canonical URLs, not ephemeral database document IDs.

## Method

1. Collect the 35 snapshots, saving all candidate IDs, URLs, both orderings,
   raw rank scores, mode, query stratum and corpus statistics.
2. Create a pooled judgment file for the **union of the two top-10 lists**
   on each query. The judgment file alphabetizes URLs and shows titles,
   not either scorer's ordering, to reduce ranking-induced label bias.
   Label URL relevance independently:
   `0=irrelevant`, `1=marginal`, `2=useful`, `3=ideal`.
3. Add relevant URLs discovered **independently of the candidate pool** to
   the judgment file. Without them, retrieval recall is optimistically biased.
   Do not infer relevance from BM25/PG scores or result ordering.
4. Explicitly mark `no_relevant_documents=true` only when verified.
   Null/missing grades are not treated as irrelevant.
5. Run the offline scorer. It refuses a complete aggregate until all pooled
   top-10 URLs have judgments and each query has at least one known relevant
   document, or an explicit no-relevant confirmation.
6. Inspect per-stratum output, zero-candidate queries, metadata/filtering
   correctness and regressions; then compare macro scores. No choice of
   production ranker is justified by aggregate alone.

### Metric definitions

For query (q), let (R_q) be independently known relevant URL identities
(graded 1–3) in the frozen corpus. Let (C_q) be the **union** of retrieval
candidates from up to 100 per channel.

- **Judged candidate recall at 100/channel:** `|R_q ∩ C_q| / |R_q|`.
  This is *not* exhaustive corpus Recall@100 and is undefined if `R_q` is
  empty. The full relevant set may be larger than the judged set.
- **P@10:** number of distinct URLs with grade > 0 among the first ten
  result positions divided by **10**. Short lists are penalized.
- **MRR@10:** `1 / rank` of the first grade > 0, else zero when there is
  at least one known relevant URL. Undefined when there are no positives.
- **nDCG@10:** `DCG/IDCG`, where
  `DCG=sum((2^grade - 1)/log2(rank + 1))`, and IDCG sorts all judged
  positive grades from high to low, truncating at 10. Undefined without
  positives. Duplicate URLs only gain once.
- **Macro average:** arithmetic mean of the defined per-query values.
  No-positive queries are omitted for recall/MRR/nDCG (not P@10);
  zero-candidate query rate is reported separately.

A fully judged, **independently sourced** qrel set is required to make a
reliable claim about the retrieval budget. The pooled top-10 labels are
sufficient to compare the two rankings *within the same pool*, not to assert
full-corpus retrieval recall.

## Reproduce

From `backend/` (set `DATABASE_URL` for the frozen local PostgreSQL corpus):

```bash
poetry run pytest tests/unit/test_relevance_metrics.py tests/unit/test_ranking_goldens.py -v
poetry run pytest tests/integration/test_ranking_developer_queries.py -v -rs

poetry run python ../scripts/evaluate_relevance.py collect \
  --corpus-id <frozen-database-id> \
  --queries evaluation/queries.json \
  --snapshot reports/exp-0004-snapshot.json \
  --judgment-template reports/exp-0004-qrels.json

# Open reports/exp-0004-qrels.json, manually fill null grades (0..3).
# Add independently verified relevant URLs that may be absent from the pool.
# For genuine zero-relevant queries, set no_relevant_documents=true.
poetry run python ../scripts/evaluate_relevance.py score \
  --snapshot reports/exp-0004-snapshot.json \
  --qrels reports/exp-0004-qrels.json \
  --output reports/exp-0004-results.json
```

`score` needs no database. It returns exit code **2** and writes a clearly
marked `incomplete` report if judgments remain unfinished. Store the
snapshot, completed judgments, result JSON, server/Python/PG versions, and
corpus identity together as evidence for the experiment. Never publish
fabricated or auto-assigned grades.

## Results

**Implementation:** the collector, macro scorer, query manifest, validation,
unit metric tests and deterministic BM25 golden score/order fixtures exist on
`feat/exp-0004-relevance-evaluation`.

**Real judged experiment:** NOT YET RUN. No frozen live-corpus snapshot,
independently reviewed qrels, measured P@10, MRR@10, nDCG@10 or judged recall
was available for this record. Do not interpret unit-test fixture numbers as
production quality.

| Evidence | State |
| --- | --- |
| 35-query manifest | prepared |
| Candidate-level PG/BM25 comparison | implemented |
| P@10, MRR@10, nDCG@10, judged recall evaluator | implemented |
| Frozen synthetic BM25 golden scores/order | implemented |
| Real query judgment set | **pending independent review** |
| Actual live-corpus scored aggregate | **pending** |
| Recall gate for arbitrary documents beyond 20k pool | **not established** |

## Analysis

Even with complete top-10 pooled judgments, qrels may omit relevant results
outside the 100/channel candidate budget. Report **judged recall**, not
full-corpus recall. The unordered 20k pre-ranking pool and the difference
between text normalization 0 and code normalization 32 should be reviewed as
separate search-quality experiments. An `ALL`-mode additive score is not
BM25F, nor is its calibration established here.

## Outcome

**Inconclusive.** This PR provides reproducible experiment instrumentation,
not proof that BM25 beats PostgreSQL. Finish and freeze manual labels, run
on a controlled corpus, review regression strata, then choose `adopt` or
`reject` in a follow-up revision. Keep ranking tradeoffs visible in ADR-0028.
