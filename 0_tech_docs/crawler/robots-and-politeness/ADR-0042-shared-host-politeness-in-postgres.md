---
id: ADR-0042
title: Enforce host politeness across processes with a crawl_host row and one atomic claim
status: accepted
date: '2026-11-05'
area: crawler
feature: robots-and-politeness
code:
- crawler/src/crawler/policy_and_politeness/shared_politeness.py
- crawler/src/crawler/scheduler/repository.py
- crawler/src/crawler/worker/runner.py
- backend/src/backend/models/crawl_host.py
- backend/alembic/versions/a1c4e7d2b9f0_crawl_host_scheduling.py
supersedes: null
superseded_by: null
related:
- ADR-0017
- EXP-0001
- EXP-0008
---

# ADR-0042: Enforce host politeness across processes with a crawl_host row and one atomic claim

## TL;DR

Every host has one `crawl_host` row. A claim leases a target and holds its host in one SQL statement, so workers never pick up work for a busy host. Any number of crawler processes now share one gap, one in-flight request and one backoff per host.

## Context

ADR-0017 kept the limiter in memory, so politeness only held inside one process. EXP-0008 measured what that means: 4 processes broke the gap on 99% of requests, at 3.9 times the allowed rate. Reaching 2M documents needs more than one process. The hosting budget rules out a separate queue or Redis.

## Decision

- `crawl_host(host, next_allowed_at, backoff_until)` holds shared state. `crawl_target.host` is a generated column, and a statement trigger registers new hosts, so no writer can forget.
- A claim picks ready hosts, longest waiting first, takes one due target from each, leases it and pushes `next_allowed_at` forward by a 60 second hold. All of this is one statement.
- Finishing a request sets `next_allowed_at` to now + the gap. So the gap is measured from the end of a request, and a host has one request in flight at most.
- A crashed worker needs no cleanup. Its hold just expires.
- The claim pays for the job's first request. Later requests in the same job (the page after robots.txt, redirects) take the host through `SharedPolitenessManager`.
- 429 and 503 set `backoff_until` for every process.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| crawl_host row plus host-aware claim | No new infrastructure, atomic, survives crashes | One more write per request | chosen |
| Keep source round robin, gate at fetch time | Smaller change | Slots sit idle waiting on one busy host | rejected |
| Redis token bucket | Very fast | A new service to run and pay for | rejected for this scale |
| Reserve future time slots | Fair queueing | Jobs sleep while their leases run out | rejected |

## Why

The bottleneck was never database speed. It was workers holding slots for hosts they could not fetch yet. Choosing by host means a free slot always goes to a host that can be fetched now.

## Consequences

- Gained: a measured 0 violations at 8 processes, and 204 requests/s across 200 hosts with 4 processes.
- Accepted limitations / tech debt: claims choose by host, so round robin by source is gone. A source with many hosts gets more of the crawl. `source.last_claimed_at` is no longer written.
- Claims cost one index probe per ready host. That is fine for thousands of hosts, and it needs another look past tens of thousands.
- Crawl rate is now limited by host count. 2 seconds per host means 100 hosts give 50 requests/s at most.

## Invariants

- Choose hosts before locking any target. Locking inside the sorted query locks one target of every ready host, not just the LIMIT (found in testing).
- One target per host per claim.
- No database connection is held across an HTTP request.
- Politeness state lives only in `crawl_host`. Do not add a second limiter.

## Evidence

- [`crawler/tests/benchmarks/fake_web_load.py`](../../../crawler/tests/benchmarks/fake_web_load.py) and [EXP-0008](../../infra/performance-and-scaling/EXP-0008-crawl-index-search-at-2m.md).
- [`crawler/tests/crawler/policy_and_politeness/test_shared_politeness.py`](../../../crawler/tests/crawler/policy_and_politeness/test_shared_politeness.py)
- [`crawler/tests/crawler/scheduler/test_concurrent_claims.py`](../../../crawler/tests/crawler/scheduler/test_concurrent_claims.py)

## Question for nish

Should a source with many hosts keep a fair share against single-host sources, or is fairness per host what you want? I assumed per host.

## Revisit when

- Hosts pass about 50,000, or claim time shows up in the admin dashboard.
- We want a per-host gap, for example from robots.txt `Crawl-delay`. Add a column to `crawl_host`.
