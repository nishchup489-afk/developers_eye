# Configuration and secret handling

Area: infra · Status: active

## Purpose

Documents environment ownership, runtime validation and credential boundaries. The existing key-exposure incident remains open; this documentation update does not rotate credentials or prove that rotation occurred.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`backend/src/backend/core/config.py`](../../../backend/src/backend/core/config.py)
- [`crawler/src/indexer/config.py`](../../../crawler/src/indexer/config.py)
- [`backend/src/backend/search/config.py`](../../../backend/src/backend/search/config.py)
- [`frontend/lib/admin-session.ts`](../../../frontend/lib/admin-session.ts)

## How-it-works docs

- [`backend/.env.example`](../../../backend/.env.example)
- [`frontend/.env.example`](../../../frontend/.env.example)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0035](../local-dev-and-testing/ADR-0035-configuration-and-validation-boundaries.md) | decision | Keep configuration explicit and distinguish test tiers from deployment evidence | accepted |
| [INC-0006](INC-0006-reporting-api-key-committed-to-git.md) | incident | Live CRAWLER_REPORT_API_KEY committed to git in crawler/src/crawler/.env.local | open |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Never commit real secrets; only `*.env.example` (INC-0006).
- After adding an ignore rule for a file that was ever committed, `git rm --cached` it (INC-0006).
- When a secret reaches git, rotate it first (INC-0006).
- Report exactly which checks ran, which skipped and which need PostgreSQL.
- Keep the backend-to-crawler dependency direction unchanged.
