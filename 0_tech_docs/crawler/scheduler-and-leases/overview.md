# Scheduler and leases

Area: crawler · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/crawler/schedular/`

## How-it-works docs
- `crawler/src/crawler/schedular/DOCS/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] PostgreSQL as the job queue instead of an external broker
- [ ] Claim ordering `priority DESC, next_fetch_at, id` with `FOR UPDATE SKIP LOCKED` (see `crawler/faced_problems.md`)
- [ ] Exponential backoff with `failure_count`
- [ ] Lease recovery for expired leases

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
