---
id: EXP-0002
title: Vocabulary worker prototype versus indexer-owned projection
status: done
outcome: reject
date: '2026-11-02'
area: indexer
feature: vocubulary
informs:
- ADR-0002
- ADR-0036
code:
- crawler/src/indexer/vocabulary.py
- backend/src/backend/models/vocabulary_document_state.py
---

# EXP-0002: Vocabulary worker prototype versus indexer-owned projection

## Question

Did the separate vocabulary-worker prototype provide a necessary responsibility that could not live in the existing index transaction?

## Why it matters

This explains why the project stopped building another worker despite already adding selector/builder/configuration/state scaffolding.

## Setup

- Hardware / OS: not recorded; this is an architectural prototype review, not a performance benchmark.
- Versions: inspect the historical commits below; no executed runtime version is inferred from commit messages.
- Data: no retained comparative corpus or run logs.
- Configuration: initial independent vocabulary work, later replaced by vector-derived deltas.

## Method

- Baseline: prototype commits 18ca1db, de8f0cc, 44e1862, 72e4127, 354d6fe.
- Variable: move vocabulary ownership into indexer transactions using stored index lexemes.
- Metrics: responsibility duplication, count consistency boundaries and required process/state ownership, assessed qualitatively.
- Runs per variant: no quantitative runs retained.

## Reproduce

From a full Git checkout, inspect the prototype and replacement without running maintenance:

```bash
git show --stat 18ca1db
git show --stat a8b1b03
git show --stat 3c79866
git show --stat c0d1690
```

Compare the prototype to current vocabulary.py and the one-shot rebuild. Do not claim those commands reproduce a throughput experiment.

## Results

| Observation | Evidence |
| --- | --- |
| Independent vocabulary prototype was built | [18ca1db](https://github.com/nishchup489-afk/developers_eye/commit/18ca1dbc30140360a43b7afe103f005616d8e4d5) through [354d6fe](https://github.com/nishchup489-afk/developers_eye/commit/354d6fe97cc0c570b35596750ac2586a82d2d33b) |
| Direction was abandoned | [a8b1b03](https://github.com/nishchup489-afk/developers_eye/commit/a8b1b0329a5cd43a9f55d27f2decc13fa2355620) |
| Indexer-owned deltas and later repair merged | PR [#3](https://github.com/nishchup489-afk/developers_eye/pull/3), PR [#4](https://github.com/nishchup489-afk/developers_eye/pull/4) |
| Current remnants | vocabulary_document_state model; named migration has empty upgrade |

## Analysis

The extra worker would require an independent freshness/replay state and could tokenize differently from PostgreSQL. The replacement avoids that split. This does not establish that incremental maintenance is bug-free: INC-0007 remains open.

## Outcome

Reject the standalone worker for the current architecture; retain transactional index-derived vocabulary and an explicit repair CLI. No relative speed, cost or memory improvement was measured.
