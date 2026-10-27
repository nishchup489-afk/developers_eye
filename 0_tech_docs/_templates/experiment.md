---
id: EXP-XXXX
title: <what we measured>
status: done            # planned | running | done
outcome: inconclusive   # adopt | reject | inconclusive
date: YYYY-MM-DD
area: crawler
feature: <feature folder>
informs: []             # ADR ids this experiment feeds
---

# EXP-XXXX: <Experiment title>

## Question
<!-- required: one falsifiable claim, e.g. "SKIP LOCKED keeps p95 claim under 50 ms with 8 workers" -->

## Why it matters
Which decision this informs.

## Setup
- Hardware / OS:
- Versions (Python, Postgres, libraries):
- Data size and source:
- Configuration:

## Method
- Baseline:
- Variable changed:
- Metrics:
- Runs per variant:

## Reproduce
<!-- required -->
```
exact commands
```

## Results
<!-- required: real numbers, tables, links to raw logs -->

## Analysis
Did the results support the claim? Confounders and limits.

## Outcome
Adopt | Reject | Inconclusive, and the follow-up (new ADR, next experiment).
