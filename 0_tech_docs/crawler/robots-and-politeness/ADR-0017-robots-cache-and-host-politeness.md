---
id: ADR-0017
title: Cache robots per origin and coordinate conservative host pacing
status: accepted
date: '2026-11-02'
area: crawler
feature: robots-and-politeness
code:
- crawler/src/crawler/policy_and_politeness/robots_policy.py
- crawler/src/crawler/policy_and_politeness/robots_rules.py
- crawler/src/crawler/policy_and_politeness/politeness_policy.py
- backend/src/backend/models/robot_cache.py
supersedes: null
superseded_by: ADR-0042
related:
- INC-0004
- ADR-0006
- ADR-0038
---

# ADR-0017: Cache robots per origin and coordinate conservative host pacing

## TL;DR

Persist robots.txt decisions by origin and pace requests by normalized host. The limiter is explicitly local to one event loop, so adding worker processes requires shared host coordination.

## Context

Repeated robots fetches waste upstream capacity; concurrency without spacing can still overload a host. The stdlib robots parser previously missed wildcard rules (INC-0004).

## Decision

Robots cache TTL defaults to 24 hours, with bounded fetch/redirect handling and a 300-second default defer for transient uncertainty. Use the project longest-match/wildcard rules. Politeness defaults are two in-flight requests per host, two seconds between starts, 60-second fallback backoff and a 3,600-second cap. Parse Retry-After as seconds or date. Host keys span schemes/ports; robots keys retain the origin distinction.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Persistent robots plus local host limiter | Simple and conservative for one process | Not a cluster-wide rate limit | chosen |
| Robots network request for every target | Fresh policy | Extra upstream work and latency | rejected |
| Uncoordinated extra worker processes | Higher nominal concurrency | Multiplies per-host traffic limits | rejected until shared limiter exists |

## Why

Robots permission and request pacing answer different questions and need separate state, keys and failure behavior.

## Consequences

- Gained: Reusable permission decisions and bounded host pressure.
- Accepted limitations / tech debt: Cache expiry can delay policy changes; local state does not coordinate another process or host.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- Denied destinations are not fetched.
- Each response body retains its host slot until closed.
- Retry-After is interpreted within the configured bounded policy.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run.

- [`crawler/src/crawler/policy_and_politeness/robots_policy.py`](../../../crawler/src/crawler/policy_and_politeness/robots_policy.py)
- [`crawler/src/crawler/policy_and_politeness/robots_rules.py`](../../../crawler/src/crawler/policy_and_politeness/robots_rules.py)
- [`crawler/src/crawler/policy_and_politeness/politeness_policy.py`](../../../crawler/src/crawler/policy_and_politeness/politeness_policy.py)
- [`backend/src/backend/models/robot_cache.py`](../../../backend/src/backend/models/robot_cache.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests/crawler/policy_and_politeness`](../../../crawler/tests/crawler/policy_and_politeness)

## Revisit when

- Before running a second crawler process against overlapping hosts.
- A source changes robots often enough that the current TTL causes operational issues.

## Rules for future changes

- Do not advertise local semaphores as distributed politeness.
- Keep wildcard/longest-match fixtures and robots-cache expiry tests.
