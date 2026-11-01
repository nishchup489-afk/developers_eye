# Configuration and secrets

Area: infra · Status: active

## Purpose
How each package gets its settings and secrets: `backend` reads `backend/.env` through pydantic-settings, the indexer reads only the process environment, the frontend reads `frontend/.env.local`. Only `*.env.example` files belong in git.

## Code
- `backend/src/backend/core/config.py`
- `crawler/src/crawler/config.py`

## How-it-works docs
- _none yet_

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [INC-0006](INC-0006-reporting-api-key-committed-to-git.md) | incident | Live reporting API key committed to git | open |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [ ] Env file layout per package
- [ ] Leaked reporting key in git history (rotate and untrack): recorded as INC-0006, still open

## Rules for future changes
- Never commit real secrets; only `*.env.example` (INC-0006).
- After adding an ignore rule for a file that was ever committed, `git rm --cached` it (INC-0006).
- When a secret reaches git, rotate it first (INC-0006).
