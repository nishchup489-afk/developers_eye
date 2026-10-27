---
id: INC-XXXX
title: <what broke, in a few words>
status: resolved        # open | mitigated | resolved
date: YYYY-MM-DD
severity: low           # low | medium | high | critical
area: crawler
feature: <feature folder>
code: []
fix_commits: []
related: []             # ADRs this changed or created
---

# INC-XXXX: <Incident title>

## Signature
<!-- required: the exact error, log line or symptom someone would search for -->
```
paste the error / log line here
```

## Summary
<!-- required -->
What happened and what the impact was (data lost, crawl stalled, wrong results, hours spent).

## Expected vs actual
- Expected:
- Actual:

## Timeline
<!-- optional -->
How it was detected, then what happened in order.

## Root cause
<!-- required -->
The real cause and the evidence that proves it.

## Fixes that did not work
<!-- required if any were tried: this is the most valuable part for the next person -->
| Attempt | Why it failed |
| --- | --- |

## Resolution
<!-- required -->
What changed and why it addresses the root cause.

## Prevention
- Regression test:
- Monitoring / alert:
- Design change (ADR):
- Remaining risk:

## Rules for future changes
<!-- required: copy into the feature overview.md -->
- 
