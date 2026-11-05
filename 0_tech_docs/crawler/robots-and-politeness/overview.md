# Robots and politeness

Area: crawler · Status: active

## Purpose

Caches robots policy per origin and applies pacing per normalized host. Request concurrency and spacing are local to one process; overlapping crawler processes need shared coordination.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/policy_and_politeness/robots_policy.py`](../../../crawler/src/crawler/policy_and_politeness/robots_policy.py)
- [`crawler/src/crawler/policy_and_politeness/politeness_policy.py`](../../../crawler/src/crawler/policy_and_politeness/politeness_policy.py)

## How-it-works docs

- [`crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md`](../../../crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md)
- [`crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md`](../../../crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0042](ADR-0042-shared-host-politeness-in-postgres.md) | decision | Enforce host politeness across processes with a crawl_host row and one atomic claim | accepted |
| [ADR-0017](ADR-0017-robots-cache-and-host-politeness.md) | decision | Cache robots per origin and coordinate conservative host pacing | accepted |
| [INC-0004](INC-0004-stdlib-robots-parser-ignored-wildcards.md) | incident | Python's urllib.robotparser ignored wildcard Disallow rules and longest-match Allow | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Do not go back to `urllib.robotparser` or any parser without RFC 9309 longest-match and wildcards (INC-0004).
- Every change to `robots_rules.py` comes with a test holding the exact robots.txt text and URL (INC-0004).
- Keep passing: `tests/test_robots_rules.py`, `tests/test_robots_policy.py`.
- Politeness state lives only in `crawl_host`. Do not add a second limiter (ADR-0042).
- Keep wildcard/longest-match fixtures and robots-cache expiry tests.
