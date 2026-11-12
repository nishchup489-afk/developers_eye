# Frozen 25-query real-corpus benchmark

This is an **agent-reviewed editorial baseline**, not a human user study. It
contains 25 queries over the local 100,141-row index, 328 query/document grades,
and frozen BM25/PostgreSQL rankings. No ranking weights were changed to obtain
these results. See [EXP-0014](../../../0_tech_docs/backend/ranking/EXP-0014-agent-reviewed-25-query-baseline.md).

| Metric | BM25 @5 | PostgreSQL @5 | BM25 @10 | PostgreSQL @10 |
| --- | ---: | ---: | ---: | ---: |
| Precision | 0.776 | 0.832 | 0.736 | 0.780 |
| MRR | 0.900 | 0.920 | 0.900 | 0.927 |
| nDCG | 0.648 | 0.624 | 0.707 | 0.688 |

Judged candidate recall is 0.9415 for both scorers because they rerank the same
candidate set. It is **not exhaustive corpus recall or global Recall@100**.

## Files and reproduction

- `queries.json`: fixed queries, modes, source restrictions, and strata.
- `snapshot.json`: frozen candidate identities and both ranking outputs.
- `qrels-template.json`: alphabetical ungraded pool, retained to show the review input.
- `qrels.json`: grades, rubric, assessor, independent reference checks, and limitations.
- `results-at-5.json`, `results-at-10.json`: reproducible offline scores.

From the repository root, using a Python environment with backend installed:

```powershell
python scripts/evaluate_relevance.py score --snapshot backend/evaluation/checklist-25/snapshot.json --qrels backend/evaluation/checklist-25/qrels.json --cutoff 5 --output backend/evaluation/checklist-25/results-at-5.json
python scripts/evaluate_relevance.py score --snapshot backend/evaluation/checklist-25/snapshot.json --qrels backend/evaluation/checklist-25/qrels.json --cutoff 10 --output backend/evaluation/checklist-25/results-at-10.json
```

Scoring uses neither PostgreSQL nor the network. To collect another run, use the
same query manifest and new snapshot/template paths; do not overwrite these grades.
Keep corpus revisions comparable before attributing a metric change to code.

## Review method and limits

Grades were assigned from alphabetically sorted canonical URLs, source titles,
and query-relevant excerpts from locally stored content. The local evidence
file's hash is retained in the qrels. One exception to blinding is explicit:
the first five live `FastAPI Depends` results had been seen earlier during
language-preference validation; scorer scores were not used for judging.

Grade 0 is irrelevant, 1 marginal, 2 useful, and 3 ideal for the query intent.
The existing precision/recall contract treats every grade above 0 as relevant;
nDCG distinguishes usefulness. Missing result positions count as nonrelevant,
so narrow identifier queries with only one good match have low P@10 even when
that match is first. This is a diagnostic, not a launch acceptance threshold.

The pool combines both top-10 lists. Independently selected reference URLs were
checked for availability and index membership: 22 were present, three MDN
references were missing. Only present references were added as positives. Six
additional query/document pairs were outside the original pooled lists. The
misspelled `pyhton asyncio` query retains a known relevant asyncio reference;
its empty retrieval is scored as a miss rather than mislabeled as no relevant
documents. Source categories are 24 Docs queries and one GitHub query, so this
does not establish discussion/article relevance or multilingual usability.

No full database snapshot is included. Stored-content review happened after
ranking collection; the qrels retain observed reference revisions. Independent
human judgments and a held-out query set are still needed before tuning weights.
