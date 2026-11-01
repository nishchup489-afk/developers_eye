---
id: INC-0006
title: Live CRAWLER_REPORT_API_KEY committed to git in crawler/src/crawler/.env.local
status: open
date: 2026-10-20
severity: high
area: infra
feature: configuration-and-secrets
code:
  - crawler/src/crawler/.env.local
  - crawler/src/crawler/.env
  - crawler/src/crawler/.env.production
  - crawler/src/crawler/.gitignore
  - .gitignore
fix_commits: []
related: []
---

# INC-0006: Live reporting API key committed to git

## Signature
```
git ls-files | grep '\.env'
crawler/src/crawler/.env
crawler/src/crawler/.env.local
crawler/src/crawler/.env.production
```

## Summary
`crawler/src/crawler/.env.local` is tracked by git (first added in `fc34675` on 2026-10-08, changed in `5752803` on 2026-10-20) and contains `CRAWLER_REPORT_API_KEY`. That key is the single bearer token protecting every `/admin/*` route on the backend. It is pushed to `origin/main`. As of 2026-11-01 the value in that file is still identical to the one in `backend/.env` (checked by comparing hashes, not by printing it), so **the key has not been rotated**. Anyone with read access to the repository can read every admin report: crawl history, stored documents, attempts and errors.

`crawler/src/crawler/.env` and `.env.production` are tracked too.

> **Question for nish:** is the GitHub repository public or private? That decides how urgent rotation is. Either way, the key should be rotated.

## Expected vs actual
- Expected: only `*.env.example` files are tracked; real values live in untracked files.
- Actual: three real env files under `crawler/src/crawler/` are tracked, one with the live admin key.

## Root cause
1. The files were committed in the very first crawler commit, before any ignore rules covered them.
2. Once a file is tracked, `.gitignore` no longer applies to it. The ignore rules added later (`.env*.local` at the root, `*.env` and `*.env.local` in `crawler/src/crawler/.gitignore`) match these names but cannot untrack them. (The handoff suspected the crawler patterns do not match `.env.local`; in gitignore `*` can match an empty string, so they do. Tracking is the real cause.)
3. The same key value is shared between `backend/.env`, `frontend/.env.local` and this file, so the crawler copy is a copy of a live production secret rather than a separate test value.

> **Question for nish:** does the crawler actually read `CRAWLER_REPORT_API_KEY` from its own `.env.local` any more? Since the reporting moved into the backend (ADR-0012), the crawler copy may not be needed at all.

## Fixes that did not work
| Attempt | Why it failed |
| --- | --- |
| Adding ignore patterns (`.env*.local`, `*.env`, `*.env.local`) | Ignore rules do not affect files that are already tracked. |

## Resolution
**Not done yet.** Steps, in order:
1. Generate a new key (32+ random characters) and put it in `backend/.env` and `frontend/.env.local`. Restart both. The old key stops working immediately.
2. `git rm --cached crawler/src/crawler/.env crawler/src/crawler/.env.local crawler/src/crawler/.env.production` and commit. Keep `.env.example`.
3. Optional: rewrite history (`git filter-repo`) to remove the old values. This only matters if the old key is still valid somewhere; after step 1 it is not, so rotation is the real fix.

## Prevention
- Regression test: none. A cheap check is a CI step (or pre-commit hook) that fails if `git ls-files` lists any `.env` file other than `*.env.example`.
- Monitoring: none. The backend does not log failed admin auth attempts.
- Design change: one shared key for all admin routes (`backend/admin-api` decision to record) means one leak exposes everything.
- Remaining risk: until step 1 is done, the admin API is effectively unauthenticated for anyone who can read the repository.

## Rules for future changes
- Never commit a file with real secrets; only `*.env.example` with placeholder values.
- After adding an ignore rule for a file that was ever committed, run `git rm --cached` on it.
- When a secret reaches git, rotate it first; cleaning history is secondary.
- Do not reuse the same secret value across services' env files unless they genuinely need the same one.
