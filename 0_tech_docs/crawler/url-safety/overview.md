# URL safety (SSRF, DNS, redirects)

Area: crawler · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/crawler/policy_and_politeness/host_policy.py`
- `crawler/src/crawler/policy_and_politeness/dns_policy.py`
- `crawler/src/crawler/policy_and_politeness/redirect_policy.py`
- `crawler/src/crawler/policy_and_politeness/policy_coordinator.py`

## How-it-works docs
- `crawler/src/crawler/policy_and_politeness/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Two-stage URL validation: cheap allowlist first, then DNS
- [ ] Block private IP ranges and pin resolved IPs against DNS rebinding
- [ ] Re-check policy on every redirect hop

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
