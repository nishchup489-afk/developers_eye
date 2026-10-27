# Robots.txt and politeness

Area: crawler · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/crawler/policy_and_politeness/robots_policy.py`
- `crawler/src/crawler/policy_and_politeness/robots_rules.py`
- `crawler/src/crawler/policy_and_politeness/politeness_policy.py`

## How-it-works docs
- `crawler/src/crawler/policy_and_politeness/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] robots.txt cached per origin in `robots_cache` with expiry
- [ ] Per-host delay and concurrency limits

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
