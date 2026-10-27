# Worker runtime

Area: crawler · Status: stub

## Purpose
_One paragraph: what this feature is responsible for and what it is not._

## Code
- `crawler/src/crawler/worker/runner.py`
- `crawler/src/crawler/worker/jobs/`
- `crawler/src/crawler/worker/recovery.py`

## How-it-works docs
- `crawler/src/crawler/worker/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] One target through the whole pipeline in one lease-safe transaction
- [ ] Never claim more than the worker can start immediately
- [ ] Job timeout at least 15 s under the lease; deadlock retry
- [ ] Each attempt records its own lease so recovery closes only its attempts

## Rules for future changes
_Short, enforceable rules distilled from the records above. Agents read this first._
