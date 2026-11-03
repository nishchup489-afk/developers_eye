---
id: INC-0013
title: CRAWLER_API_KEY was exposed in commit "https://github.com/nishchup489-afk/developers_eye/commit/5752803e81edc07f33e6f183d88dda3100cc7000" [feat: reporting frontend added]
status: resolved        # open | mitigated | resolved
date: YYYY-MM-DD
severity: high           # low | medium | high | critical
area: crawler
feature: backend/api
code: []
fix_commits: []
related: []             # ADRs this changed or created
---

# INC-XXXX: <Incident title>

## Signature
<!-- required: the exact error, log line or symptom someone would search for -->
```
exposure_commits:
  - 5752803e81edc07f33e6f183d88dda3100cc7000
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

## fixes 
(crawler) PS C:\Users\nishc\Documents\developers-eye> & .\crawler\.venv\Scripts\python.exe .\temp_test.py
Previously exposed key: 
New API key: 
Old key HTTP status: 401
New key HTTP status: 200
PASS: rotation verified locally.


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
