---
id: EXP-0017
title: Title-match channel and dotted identifiers recover recall misses
status: done
outcome: adopt
date: 2026-11-10
area: backend
feature: retrieval
informs: [ADR-0024]
---

# EXP-0017: Title channel and dotted identifiers

## Question
Of the ten 100k-run queries whose expected page never reached the candidate pool, a title-match channel
(top 30 documents whose title holds at least half the query terms) and matching `asyncio.semaphore`-style
lexemes from space-separated queries bring at least eight into the pool, without slowing typical searches
by more than about 100 ms.

## Why it matters
The 100k run missed expected targets for 10 queries (up from 6). A page that never enters the candidate
pool cannot be ranked, so ranking work cannot fix it.

## Setup
- 42,114-document dump (8 Nov), PostgreSQL 16, and the 126k scaled copy for timing.
- Misses: Q015, Q017, Q055, Q058, Q059, Q061, Q062, Q063, Q072, Q079 from the 100k run.

## Method
- Baseline: production retrieval before the change (full-text, code and fuzzy channels).
- Variable changed: `search_titles` (new channel, every mode) and `dotted_alternatives` in the code channel.
- Metric: position of the expected page in the title or code channel; per-query search time.

## Reproduce
```
PYTHONPATH=backend/src DATABASE_URL=postgresql+asyncpg://... python backend/evaluation/exp-0017/titleprobe.py out.json
```
Raw results: `backend/evaluation/exp-0017/title-probe-42k.json`.

## Results
| Query | Expected page | Result |
| --- | --- | --- |
| Q017 asyncio Semaphore | Synchronization Primitives | code channel position 1 (dotted lexeme `asyncio.semaphore`) |
| Q055 javascript event loop | event loop | title channel position 1 |
| Q058 javascript optional chaining | Optional chaining | title channel position 1 |
| Q059 javascript Object.entries | Object.entries | title channel position 1 |
| Q061 HTTP 404 | 404 Not Found | title channel position 1 |
| Q062 HTTP 500 internal server error | 500 Internal Server Error | title channel position 1 |
| Q063 HTTP caching Cache-Control | Cache-Control | title channel position 1 |
| Q079 Rust pattern matching | Patterns | title channel position 1–2 |
| Q015 asyncio TaskGroup | Coroutines and Tasks | already code position 1 at 42k; the 100k miss is a pool-size effect |
| Q072 Rust lifetimes | Lifetimes | page is not in the 42k corpus; cannot be tested here |

On the 42k diagnosis run Q017 moved from missed to found. Timing on the 126k copy: the title pass adds
tens of ms to typical queries; the broad `python OR javascript` case costs about 380 ms in the title pass
(771 ms total), because its full-query pool is about 20k documents.

## Analysis
8 of the 10 misses now enter the pool; Q015 and Q072 could not be reproduced at 42k. Limits: the real
100k corpus was not available here, so recall must be re-measured on it. Title matching favours short
titles that contain the terms, which suits reference pages but can add near-duplicate titles to the pool.

## Outcome
Adopt (commits 6ef3508, f4e82af). Follow-ups: re-run the 100k diagnosis; if broad OR queries matter, cap
the title pass's pool by rank before intersecting titles.
