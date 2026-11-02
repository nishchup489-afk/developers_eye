---
id: EXP-0004
title: Evaluate candidate recall and BM25 relevance against the FTS baseline
status: planned
outcome: inconclusive
date: '2026-11-02'
area: backend
feature: ranking
informs:
- ADR-0028
- ADR-0038
code:
- backend/src/backend/search/service.py
- backend/src/backend/search/ranking
---

# EXP-0004: Evaluate candidate recall and BM25 relevance against the FTS baseline

## Question

Does the proposed BM25 pipeline improve judged ranking without reducing candidate recall or breaking technical queries?

## Why it matters

Rarer terms alone do not prove better results; weights and truncation interact with query semantics.

## Setup

- Hardware / OS / versions: record them when the experiment runs.
- Data: freeze a versioned corpus and a manually judged query set before tuning.
- Query strata: natural-language docs, identifiers, quoted phrases, punctuation, typos, mixed code/text, stop-word-only and no-result inputs.
- Configuration: same corpus/candidate budgets, baseline ts_rank_cd versus each new scorer/configuration.

## Method

- Baseline: current get_full_text_search plus search_documents.
- Variables: one scorer/candidate budget/channel-weight change at a time.
- Metrics: Recall@candidate_limit, nDCG@10, MRR@10, zero-result rate, correction precision and p50/p95 latency.
- Runs: repeated fixed runs with warm/cold state labeled; held-out judgments for tuning decisions.

## Reproduce

Current regression checks, from backend/:

```bash
poetry run pytest src/backend/tests/integration/test_fts.py src/backend/tests/integration/test_code.py src/backend/tests/integration/test_search.py -v -rs
```

The evaluation harness, judgments and BM25 scorer do not exist yet. Before running the comparison, create versioned fixtures, record corpus/hash/config, and implement a harness that emits per-query ranked IDs and aggregate metrics. These regression commands alone do not measure relevance.

## Results

Not run. No judgments, baseline metric values or BM25 quality improvement are claimed.

## Analysis

Separate retrieval recall from reranking quality: a scorer cannot rescue a relevant document absent from candidates. Treat phrase/negation correctness and unsafe correction as correctness failures, not average-score trade-offs.

## Outcome

Inconclusive pending scorer, fixtures and execution. Keep ADR-0003 as the public baseline until a reviewed result supports replacement.
