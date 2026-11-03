---
id: ADR-0005
title: Claim order is round robin across sources, then priority and BFS depth inside a source
status: accepted
date: 2026-10-27
area: crawler
feature: scheduler-and-leases
code:
  - crawler/src/crawler/schedular/repository.py:claim_targets
  - crawler/src/crawler/frontier/priority.py:calculate_priority
  - backend/src/backend/models/source.py:last_claimed_at
  - backend/alembic/versions/5fc9efde409c_add_source_last_claimed_timestamp.py
supersedes:
superseded_by:
related: [ADR-0001, ADR-0004]
---

# ADR-0005: Round robin across sources, then priority and BFS depth inside a source

## TL;DR
`claim_targets()` first picks a source, the enabled source with due work that was claimed longest ago (`source.last_claimed_at ASC NULLS FIRST, id`), then picks that source's best target (`priority DESC, depth ASC, next_fetch_at, id`). Sources take turns inside one call and across calls. This replaced one global `ORDER BY priority DESC, next_fetch_at, id`, which let one big source fill every batch while small feeds waited.

## Context
The first claim was a single query over the whole frontier:

```sql
WHERE state = 'queued' AND next_fetch_at <= now()
ORDER BY priority DESC, next_fetch_at ASC, id ASC
LIMIT n FOR UPDATE SKIP LOCKED
```

Priority comes from `calculate_priority()`: seed 100, sitemap 90, API 85, reference path 80, guide path 70, RSS 60, other pages 50. A documentation site that published a large sitemap produced thousands of targets at 80 to 90. They filled every batch, so an RSS feed with a few targets at 60 was due but never claimed until the big source ran dry. That is starvation of small sources, and it is worst for feeds, which are the sources that change most often.

Inside a source, ordering only by priority and time also let the crawler follow one branch of a site deep before it had seen the top of the site.

> **Question for nish:** how did you notice the starvation: an empty feed in the admin monitor, a test, or reading the query? A concrete symptom (for example "the Python blog RSS had 0 documents after N hours") would make this record much stronger.

## Decision
- **Level 1, which source.** Candidate sources are `is_enabled = true` with at least one `crawl_target` where `state = 'queued' AND next_fetch_at <= now()`. They are ordered `last_claimed_at ASC NULLS FIRST, id ASC`. A source never claimed goes first; after that, whoever waited longest.
- **Level 2, which target in that source.** `ORDER BY priority DESC, depth ASC, next_fetch_at ASC, id ASC LIMIT 1`. Priority still wins first; at equal priority the shallowest page goes first, which is breadth-first order over the link graph (seed depth 0, set in `worker/jobs/utility.py`).
- **Turns inside one call.** A source that just gave a target goes to the back of an in-memory queue, so a call with `limit = 6` over sources A (3 due), B (2), C (1) returns `A B C A B A`.
- **Turns across calls.** At the end of the call each source that gave a target gets `last_claimed_at = GREATEST(last_claimed_at, <clock_timestamp() of its last claim in this call>)`. `clock_timestamp()` is used because `now()` is fixed for the transaction and would give every source in the batch the same time.
- `source_id` (runner `--source-id`) limits the claim to one source.
- How this is done without locking `source` rows is ADR-0001.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Round robin by `last_claimed_at`, then priority + depth per source | Every source with due work gets turns; BFS inside a site; one new column | More queries per claim than one global `LIMIT n`; a tiny source gets as many turns as a huge one | chosen |
| B. One global `ORDER BY priority DESC, next_fetch_at, id` (the original) | One query | Big sources starve small ones | rejected: the problem |
| C. Weighted fair queuing (turns proportional to a source weight or size) | Big sources progress faster without starving small ones | Needs a weight per source and more bookkeeping | not needed yet |
| D. Per-source quota per batch (at most k targets per source) | Simple | Still lets the first sources in priority order take every slot when there are many sources | rejected |
| E. Priority boost for long-waiting targets (aging) | No new column | Hard to tune; one big source with high priority still wins most turns | rejected |

> **Question for nish:** did you try anything before round robin (for example lowering sitemap priority or a per-source cap)? If so, add it under Options with why it did not work.

## Why
- **Fairness.** No source with due work waits more than one rotation of the other eligible sources.
- **Coverage.** BFS inside a source fetches the top pages of a site (landing, index, reference roots) before deep pages, which gives better results early in a crawl and wastes less budget when `max_pages` cuts the crawl off.
- **Priority still matters.** Seeds, sitemaps and API endpoints stay ahead of normal pages inside their source, so discovery still runs first.
- **Cost to build.** One nullable column (`5fc9efde409c`) and changes in one function.

## Consequences
- Gained: feeds and small sources are crawled while big sources still have work.
- Accepted limitations:
  - Fair per source, not per host or per amount of work: a source with 10,000 due targets gets the same share of claims as one with 3.
  - Two workers claiming at the same moment can both start with the same source (ADR-0001).
  - A disabled source or one with nothing due keeps its old `last_claimed_at`, so it jumps to the front when work appears again. That is intended.
- What depends on this: politeness (`PolitenessManager`) still enforces per-host delays after a claim; round robin only spreads claims across sources.

## Invariants
- Only enabled sources with a queued target due now are candidates.
- Source order is `last_claimed_at ASC NULLS FIRST, id ASC`.
- Target order inside a source is `priority DESC, depth ASC, next_fetch_at ASC, id ASC`.
- `last_claimed_at` only moves forward (`GREATEST`) and uses `clock_timestamp()`.

## Evidence
- Tests: `crawler/tests/crawler/schedular/test_round_robin.py` (21 checks: rotation inside a call and across calls, BFS order, `last_claimed_at` updates, skipped sources, `source_id`, lease length, validation).
- Measured: none for fairness itself. EXP-0001 measured claim throughput after the lock change.
- Commits: `e019701` (round robin BFS), `003ed97` (docs and tests), `8f63063` (lock fix, ADR-0001).
- How-it-works: `crawler/src/crawler/schedular/DOCS/REPOSITORY_README.md`.

## Revisit when
- Large sources fall far behind because small sources take as many turns (consider weights, option C).
- Per-host politeness should be decided at claim time instead of after the claim (claim targets whose host is not cooling down).
- Sources count grows into the thousands and the source query with its `EXISTS` subquery becomes the slow part of a claim.

## Rules for future changes
- Do not go back to a single global priority order without a new ADR.
- Keep `clock_timestamp()` for turn times and `GREATEST` on the update.
- Changing `calculate_priority()` values changes order inside a source only; check `test_round_robin.py` still passes.
- Keep passing: `schedular/tests/test_round_robin.py`, `schedular/tests/test_repository.py`.
