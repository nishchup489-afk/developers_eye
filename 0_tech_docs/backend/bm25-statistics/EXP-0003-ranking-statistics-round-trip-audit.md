---
id: EXP-0003
title: Static round-trip audit of batched ranking statistics
status: done
outcome: adopt
date: '2026-11-02'
area: backend
feature: bm25-statistics
informs:
- ADR-0027
code:
- backend/src/backend/search/ranking/statistics.py
---

# EXP-0003: Static round-trip audit of batched ranking statistics

## Question

Does the batch loader remove per-document/per-term database round trips from statistics loading?

## Why it matters

Distinguish a verified control-flow improvement from an unmeasured latency or QPS claim.

## Setup

- Hardware / OS: not relevant to static counting; no database benchmark was run.
- Versions: baseline 581d7b2, replacement facd333.
- Data size: symbolic candidate count C and term count T; example C=100, T=5.
- Configuration: one channel, a valid supplied corpus snapshot, nonempty IDs and terms.

## Method

- Baseline: count calls if the old single-value helpers were used in a naive loop. That caller was not an implemented request pipeline.
- Variable: batch all DF counts, and batch candidate TF/DL together.
- Metric: awaited SQL statements, not index probes, rows scanned, CPU or elapsed time.
- Runs: static source audit and reproducible arithmetic only.

## Reproduce

From the repo root:

```bash
python - <<'PYCOUNT'
import ast
from pathlib import Path
p = Path('backend/src/backend/search/ranking/statistics.py')
tree = ast.parse(p.read_text())
for node in tree.body:
    if isinstance(node, ast.AsyncFunctionDef):
        count = sum(
            isinstance(n, ast.Await)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr in {'execute', 'scalar'}
            for n in ast.walk(node)
        )
        print(node.name, count)
C, T = 100, 5
print('hypothetical naive helper composition:', 2 + T + C * (1 + T))
PYCOUNT
```

Inspect the loader helper calls and early returns as well; counting direct awaits alone does not capture transitive calls.

## Results

| Case | SQL statements for statistics only |
| --- | ---: |
| One channel, candidates and terms | 2 |
| One channel, candidates but no terms | 1 |
| No candidate IDs | 0 |
| Both channels, nonempty inputs, loaded sequentially | 4 |
| Separate corpus refresh for one channel | 1 full-corpus aggregation |
| Hypothetical old loop, C=100 and T=5, with N and avgdl queries | 607 |

## Analysis

The old-loop formula is 2+T+C(1+T); it is an illustrative composition, not a measured old /search request. UNION ALL still runs term-specific counts inside PostgreSQL. Candidate vector expansion and full-corpus scans remain expensive work. The new count excludes retrieval, document hydration, snippets, transactions and snapshot/cache refresh. No latency speedup is established.

## Outcome

Adopt batching as the component API shape; PostgreSQL correctness, corpus freshness and end-to-end performance still require validation before public integration.
