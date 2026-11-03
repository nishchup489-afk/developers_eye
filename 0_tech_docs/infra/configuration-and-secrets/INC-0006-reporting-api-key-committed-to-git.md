---
id: INC-0006
title: CRAWLER_REPORT_API_KEY Exposed in Git Commit 5752803
status: resolved
date: 2026-11-02
severity: high
area: backend
feature: admin-api
code:
  - backend/src/backend/core/config.py
  - backend/src/backend/api/crawler_report.py
  - frontend/lib/crawler-proxy.ts
  - backend/.env.example
  - crawler/src/crawler/.env.local
  - crawler/src/crawler/.env
  - crawler/src/crawler/.env.production
  - .gitignore
fix_commits:
  - 98daf6c0ca644fd46de0845f68e88876cbcd1c32
related:
  - ADR-0041
  - INC-0006
---

# INC-0006: CRAWLER_REPORT_API_KEY Exposed in Git History

## Signature

**Exposure commit:** [5752803e81edc07f33e6f183d88dda3100cc7000](https://github.com/nishchup489-afk/developers_eye/commit/5752803e81edc07f33e6f183d88dda3100cc7000)

**Commit message:** `feat: reporting frontend added`

**Sensitive configuration:**

```dotenv
CRAWLER_REPORT_API_KEY=<redacted>
```

**Verified credential-rotation result:**

```text
Old key HTTP status: 401
New key HTTP status: 200
PASS: rotation verified locally.
```

## Summary

On October 20, 2026, Developer's Eye committed an active `CRAWLER_REPORT_API_KEY` to GitHub.

The key appeared in `crawler/src/crawler/.env.local` and `backend/.env.example`.

This credential was used to authenticate requests to the FastAPI administrative reporting endpoints, including crawler monitoring and indexed-document inspection.

Because the exposed key remained in Git history, anyone with sufficient repository read access could potentially retrieve it and authenticate directly against a reachable backend.

**Impact:**
- Confidential administrative API credential exposed through source control.
- Potential unauthorized access to operational monitoring data.
- Administrative API authentication boundary weakened until the key was rotated.
- No confirmed unauthorized access, data deletion, or database modification.

The credential was subsequently rotated, and local validation confirmed that the old key returned HTTP 401 while the replacement returned HTTP 200.

## Expected vs actual

**Expected:**
- Real API keys stored outside Git.
- Only sanitized `.env.example` files committed.
- Backend admin endpoints accessible only with valid, non-compromised credentials.
- Exposed credentials immediately invalidated.
- Secret-scanning checks preventing new credential commits.

**Actual:**
- The reporting API key was committed to repository history.
- Tracked environment files retained sensitive configuration.
- Existing `.gitignore` rules did not retroactively untrack committed files.
- The old credential remained valid after its initial exposure.
- Automated secret scanning was not yet part of the original exposure-prevention process.

## Timeline

| Date | Event |
| --- | --- |
| 2026-10-08 | Commit `fc34675` initially added crawler environment files. |
| 2026-10-20 | Commit `5752803` introduced the exposed reporting API key into tracked configuration. |
| 2026-11-01 | Investigation documented the exposed credential and reported that the configured backend key still matched it. |
| 2026-11-02 | API-key rotation performed for the applicable environments, as reported by the project owner. |
| 2026-11-02 | Initial local test returned HTTP 401 for both old and new keys. |
| 2026-11-02 | Backend configuration check confirmed the replacement key was loaded correctly. |
| 2026-11-02 | Final local test returned HTTP 401 for the old key and HTTP 200 for the new key. |
| 2026-11-02 | Automated GitHub secret scanning was configured; the project owner reported no leaks detected. |
| 2026-11-02 | Commit `98daf6c` added the incident record draft and excluded `temp_test.py` from Git. |

## Root cause

The primary cause was committing active environment secrets into source control.

The exposure occurred in commit:

`5752803e81edc07f33e6f183d88dda3100cc7000`

Two configuration files contained a nonempty `CRAWLER_REPORT_API_KEY` at that revision:

- `crawler/src/crawler/.env.local`
- `backend/.env.example`

The problem persisted because `.gitignore` does not remove files Git already tracks.

Additionally, using a shared bearer credential across admin endpoints increased the impact of compromising that single secret.

**This was a credential-management failure, not an authentication-algorithm failure.**

The authentication implementation correctly rejected the previous key after rotation.

## Fixes that did not work

| Attempt | Why it failed |
| --- | --- |
| Add `.gitignore` patterns after files were tracked | Git continued tracking already committed files. |
| Remove secrets from the current working tree alone | Historical Git commits still retained the exposed value. |
| Initial credential verification | Both keys returned HTTP 401; it did not establish that the replacement worked against the running server. |
| Inline PowerShell `python -c` configuration check | Nested quoting caused a Python `SyntaxError`; the check was rerun using a PowerShell here-string. |

## Resolution

The incident was resolved operationally by replacing the exposed API credential and validating authentication against the local backend.

**Verified test:**

```text
Previously exposed key:
New API key:
Old key HTTP status: 401
New key HTTP status: 200
PASS: rotation verified locally.
```

This proves that the tested backend rejected the exposed credential and accepted the replacement.

The project owner also reported updating applicable environments and confirming that the backend and frontend use the new key without committing it.

The implementation, prevention checklist, alternatives, and future security requirements are documented separately in **ADR-0041**.

**Associated fix commit:**

`98daf6c0ca644fd46de0845f68e88876cbcd1c32`

This commit added the initial incident documentation and ignored the temporary verification script. The actual credential rotation occurred outside Git; the commit does not independently establish that rotation.

## Prevention

- **Regression test:** Verify that a revoked key returns HTTP 401 and a valid key successfully authenticates.
- **Monitoring / alert:** Automated GitHub Actions secret scanning with Gitleaks and tracked-environment-file validation.
- **Design change (ADR):** ADR-0041 defines credential rotation, secure environment storage, secret scanning, and operational safeguards.
- **Remaining risk:** The exposed value remains recoverable from historical commits unless Git history is rewritten. The tested local key is revoked, but independently verifying every external deployment is a separate operational responsibility. Secret scanning also cannot guarantee detection of every secret format.

## Rules for future changes

- Never commit real API keys, tokens, passwords, or production configuration.
- Keep `.env.example` files free of valid credentials.
- Rotate exposed credentials before treating repository cleanup as sufficient.
- Never interpret `.gitignore` as protection for already tracked files.
- Verify key revocation through an actual authenticated HTTP request.
- Keep authentication credentials on the server side.
- Preserve automated secret scanning for pushes and pull requests.
- Review ADR-0041 before changing secret storage or rotation procedures.
- Never print credentials in diagnostic logs or commit verification scripts containing real values.