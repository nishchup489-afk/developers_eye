# Developer's Eye relevance lab

**Status:** instrumentation and deterministic goldens exist; real-corpus judged
results are pending. See
[`EXP-0004`](../../0_tech_docs/backend/ranking/EXP-0004-lexical-relevance-evaluation.md)
for the experimental contract and metric definitions.

## Files

| Path | Purpose |
| --- | --- |
| `queries.json` | Fixed 35-query manifest with modes and strata |
| `../scripts/compare_rankings.py` | Detailed same-candidate PG/BM25 order comparison for one query |
| `../scripts/evaluate_relevance.py` | Snapshot a full query set, generate a pooled qrel template, score offline |
| `../src/backend/search/evaluation/metrics.py` | Pure P@10, MRR@10, nDCG@10, judged recall and macro-aggregation |
| `../tests/unit/test_relevance_metrics.py` | Known expected metric values, missing-judgment protection |
| `../tests/unit/test_ranking_goldens.py` | Exact BM25 score and order regression fixtures |

## Run

From `backend/` with a local, stable `DATABASE_URL`:

```bash
poetry run pytest tests/unit/test_relevance_metrics.py tests/unit/test_ranking_goldens.py -v
poetry run python scripts/evaluate_relevance.py collect --corpus-id local-v1 --queries evaluation/queries.json --snapshot reports/local-v1.json --judgment-template reports/local-v1-qrels.json
```

Open `reports/local-v1-qrels.json`. For **each query**, assign all displayed
candidate URL grades: 0 (irrelevant), 1 (marginal), 2 (useful), 3 (ideal).
Do not score by looking at BM25/PG scores or by treating PostgreSQL's order
as ground truth. **Add independently verified relevant documents** even when
they do not appear in either top-10 list. If no relevant documents exist in
the *frozen corpus*, mark `no_relevant_documents=true`; otherwise keep false.

```bash
poetry run python scripts/evaluate_relevance.py score --snapshot reports/local-v1.json --qrels reports/local-v1-qrels.json --output reports/local-v1-results.json
```

This command prints a two-scorer comparison and saves a machine-readable
result. It returns exit code 2 when some relevance labels are missing.
Rerunning the offline scorer does not change retrieved IDs or scores.

## BM25 golden fixture

The immutable unit fixture uses N=5, avgDL=10, k1=1.2, b=0.75,
with document frequencies `python=3` and `async=3`.

| Document ID | DL | TF(python) | TF(async) | Expected BM25 |
| --- | ---: | ---: | ---: | ---: |
| 101 | 6 | 2 | 2 | 1.670130002270298 |
| 102 | 10 | 1 | 1 | 1.077993001465374 |
| 103 | 5 | 0 | 3 | 0.9486338412895292 |
| 104 | 20 | 4 | 0 | 0.7775687223684666 |
| 105 | 9 | 0 | 0 | 0.0 |

Expected score order for `python async`: **101, 102, 103, 104, 105**.
Changing this requires explicit review, not a silent golden update.
The fixture validates scoring, **not** retrieval relevance.

## Interpretation limits

Judged candidate recall uses the known positive qrels, not an exhaustive
set of every document relevant to each query. The live backend pretruncates
FTS matches with an unordered 20,000-row subquery and ranks at most
100 hits per channel. These constraints can hide good documents from both
scorers. They should be evaluated independently before claiming full-corpus
Recall@100. The snapshot is a database-consistent observation, not
automatically a reusable database backup.
