# Robots.txt and politeness

Area: crawler · Status: active

## Purpose
Fetches, caches (`robots_cache`, per origin with expiry) and evaluates robots.txt for `DevelopersEyeBot`, and enforces per-host delays and concurrency around each request. It does not decide whether a host is safe to contact (`url-safety`).

## Code
- `crawler/src/crawler/policy_and_politeness/robots_policy.py`
- `crawler/src/crawler/policy_and_politeness/robots_rules.py`
- `crawler/src/crawler/policy_and_politeness/politeness_policy.py`

## How-it-works docs
- `crawler/src/crawler/policy_and_politeness/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [INC-0004](INC-0004-stdlib-robots-parser-ignored-wildcards.md) | incident | The standard robots parser ignored wildcards and longest-match rules | resolved |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] robots.txt cached per origin in `robots_cache` with expiry
- [ ] Per-host delay and concurrency limits

## Rules for future changes
- Do not go back to `urllib.robotparser` or any parser without RFC 9309 longest-match and wildcards (INC-0004).
- Every change to `robots_rules.py` comes with a test holding the exact robots.txt text and URL (INC-0004).
- Keep passing: `tests/test_robots_rules.py`, `tests/test_robots_policy.py`.
