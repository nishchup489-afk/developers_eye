---
id: ADR-0041
title: Rotate Exposed Credentials and Enforce Automated Secret Scanning
status: accepted
date: 2026-11-02
area: infra
feature: configuration-and-secrets
code:
  - backend/src/backend/core/config.py
  - backend/src/backend/api/crawler_report.py:require_report_key
  - frontend/lib/crawler-proxy.ts:adminProxy
  - frontend/app/api/admin/crawler/report/route.ts
  - backend/.env.example
  - frontend/.env.example
  - .github/workflows/secret-scanning.yml
  - .gitignore
  - crawler/src/crawler/worker/runner.py:main
  - crawler/src/crawler/policy_and_politeness/politeness_policy.py:PolitenessManager
supersedes:
superseded_by:
related:
  - INC-0006
  - ADR-0017
  - ADR-0032
---

# ADR-0041: Rotate Exposed Credentials and Enforce Automated Secret Scanning

## TL;DR

Developer's Eye uses server-side API credentials, mandatory rotation following exposure, and automated GitHub secret scanning to prevent administrative authentication secrets from being leaked through source control.

The immediate incident was resolved by replacing `CRAWLER_REPORT_API_KEY` and verifying that the old key returned HTTP 401 while the new key returned HTTP 200.

A separate operational risk remains: the project owner has elected to continue running multiple crawler processes while politeness limits are process-local.

## Context

Developer's Eye consists of multiple independently running components:

- FastAPI backend.
- Next.js frontend.
- PostgreSQL database.
- Crawler workers.
- Indexer workers.

The Next.js server authenticates its calls to the FastAPI admin endpoints using `CRAWLER_REPORT_API_KEY`.

This credential must be available to both services but must never appear in client-side JavaScript, logs, or Git history.

On October 20, 2026, the credential was exposed through commit `5752803`.

The incident demonstrated weaknesses in:

1. Environment-file handling.
2. Separation between configuration templates and live credentials.
3. Credential-rotation verification.
4. Automated secret detection.
5. Operational documentation of security exceptions.

The design must remain inexpensive, maintainable, and compatible with the current Python, Next.js, and GitHub toolchain.

## Decision

### A. Store admin credentials outside source control

Use the environment variable:

`CRAWLER_REPORT_API_KEY`

The backend and frontend server must use the same credential for a deployment pair.

Local configuration:

- Backend: `backend/.env`
- Frontend: `frontend/.env.local`

Production deployments must use their deployment platform's environment-variable or secret-management facilities.

Example configuration files must contain empty or explicitly invalid values.

Use separate credentials for independently deployed environments where practical.

The key must never be sent to the browser.

### B. Require cryptographically secure credentials

Generate reporting API keys using a cryptographically secure random generator.

Recommended implementation:

```python
import secrets

print(secrets.token_hex(32))
```

This produces 32 random bytes represented as 64 hexadecimal characters.

The backend requires a configured key with at least 32 characters.

The existing authentication implementation uses a timing-safe comparison to validate the supplied bearer token.

### C. Rotate credentials following exposure

When a secret is committed, logged publicly, or otherwise exposed:

1. Generate a replacement key.
2. Update every applicable backend environment.
3. Update the corresponding frontend server environment.
4. Restart or redeploy affected services.
5. Verify that the previous key returns HTTP 401.
6. Verify that the new key authenticates successfully.
7. Remove exposed configuration files from Git tracking.
8. Check all exposed files for additional credentials requiring rotation.
9. Document the exposure and remediation evidence.

Do not treat deletion of a committed file as credential revocation.

### D. Add automated secret scanning

Use GitHub Actions with Gitleaks.

Workflow:

`.github/workflows/secret-scanning.yml`

Run scanning on:

- Pushes to `main`.
- Pull requests.
- Manual workflow dispatch.

The workflow must:

- Scan repository contents and relevant Git history.
- Detect likely exposed credentials.
- Reject tracked environment files other than approved examples.
- Reject a nonempty reporting key in `backend/.env.example`.
- Fail the appropriate CI job when a violation is detected.

Gitleaks is a preventative detection layer, not proof that a repository contains no secrets.

### E. Maintain crawler politeness safeguards

The current crawler creates an in-memory `PolitenessManager` with:

```python
PolitenessManager(
    max_concurrent_per_host=1,
    min_interval_seconds=2.0,
)
```

These controls apply within each crawler process.

**Recommended safe configuration:** Run one crawler process until host-level concurrency, request spacing, and retry backoff are coordinated across processes.

**Current operational exception:** The project owner has chosen to continue running multiple crawler processes.

Therefore, the one-process safeguard is not currently enforced, even though it was administratively checked off in the remediation checklist.

This decision accepts the risk that simultaneous processes may collectively exceed the configured per-host limits.

A cross-process politeness coordinator is **planned**, not implemented.

Potential implementations include a PostgreSQL-backed host limiter or a shared Redis-based coordinator, subject to a separate design and performance evaluation.

## Remediation checklist

Recorded against INC-0006 on November 2, 2026.

- [x] Rotate `CRAWLER_REPORT_API_KEY` in every applicable environment.
- [x] Verify that the previously exposed key returns HTTP 401/403.
- [x] Check whether the key was deployed anywhere beyond local development.
- [x] Ensure backend and frontend use the new key without committing it.
- [x] Add automated secret scanning to prevent recurrence.
- [x] Keep crawling to one process until politeness is enforced across processes.

**Checklist accuracy note:** The first five items reflect the project owner's reported completion, with local HTTP evidence for credential revocation and repository evidence for the scanning workflow. The sixth item was marked complete by the owner but is intentionally not being enforced. It must not be treated as a verified safety control.

### Credential verification evidence

```text
Old key HTTP status: 401
New key HTTP status: 200
PASS: rotation verified locally.
```

### Secret scanning evidence

The project owner reported:

```text
No leaks detected
```

The workflow file exists in the inspected repository.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Rotate immediately, keep secrets server-side, add GitHub scanning | Strong immediate mitigation with minimal infrastructure | Requires ongoing workflow maintenance | Chosen |
| B. Delete the committed files without rotating the key | Easy repository cleanup | Historical key remains valid | Rejected |
| C. Rely only on `.gitignore` | Simple local configuration | Cannot protect previously tracked files or detect all secrets | Rejected |
| D. Introduce a dedicated external secret-management service immediately | Centralized secret lifecycle | Additional setup and operational cost for the current MVP | Deferred |

## Why

The chosen solution directly addresses the failure observed in INC-0006.

### Security

A leaked credential must become unusable.

Rotating the key removes its authentication capability even when historical copies remain accessible.

### Correctness

Testing both the revoked and replacement credentials verifies the intended authentication behavior.

### Reliability

Server-side environment configuration avoids unnecessary changes to the existing backend authentication protocol.

### Operability

GitHub Actions provides automated enforcement without introducing additional always-running infrastructure.

### Cost

Gitleaks and the repository's existing GitHub Actions workflow fit the current low-cost development model.

## Consequences

### Gained

- Previously exposed reporting credentials invalidated in the verified local environment.
- Working replacement authentication.
- Automated secret-scanning workflow.
- Better separation between example configuration and live secrets.
- A repeatable incident-response procedure.
- Explicit recognition of the remaining crawler concurrency risk.

### Accepted limitations / tech debt

- Compromised credentials may remain visible in historical Git commits.
- Secret scanning may miss unknown credential formats.
- Operational rotation still requires coordinated environment updates.
- Full production credential revocation is not established solely by a local HTTP test.
- Current crawler politeness is process-local.
- Running multiple crawler processes remains an explicitly accepted operational exception.
- Shared cross-process politeness is not yet implemented.

### What now depends on this decision

- Backend admin authentication.
- Frontend-to-backend administrative requests.
- GitHub security workflows.
- Environment configuration.
- Incident-response procedures.
- Future crawler deployment and scaling decisions.

## Invariants

1. No valid API key is committed to Git.
2. `.env.example` files contain no live credentials.
3. API keys remain server-side.
4. A revoked credential must fail authentication.
5. A valid credential must authenticate successfully.
6. The backend must reject missing or invalid bearer tokens.
7. Secret scanning must run on pushes to `main` and pull requests.
8. Real `.env` files must not be tracked.
9. Credential rotation must cover every environment using the exposed value.
10. The process-local politeness manager must not be represented as a distributed limiter.
11. Multi-process crawling must remain documented as an accepted risk until shared politeness is implemented.
12. No credential value may appear in incident logs, test output, or documentation.

## Failure modes

| Failure mode | Response |
| --- | --- |
| API key committed to Git | Rotate immediately and revoke the exposed value |
| Old key remains valid | Investigate all backend deployments and restart stale instances |
| New key returns HTTP 401 | Check configuration loading and frontend/backend secret agreement |
| Git history retains exposed secrets | Ensure rotation is complete; consider history rewriting where justified |
| Secret scanner misses a key | Improve scanning patterns and add additional checks |
| Secret scanner reports a false positive | Investigate and document before any narrow exception |
| Multiple crawlers exceed host politeness limits | Monitor responses, throttle concurrency, or implement a shared limiter |

Related incident: INC-0006.

## Evidence

### Measured / verified

**Exposure:**

Commit `5752803e81edc07f33e6f183d88dda3100cc7000` contained a nonempty reporting API key in tracked configuration.

**Rotation:**

```text
Old key HTTP status: 401
New key HTTP status: 200
PASS: rotation verified locally.
```

**Repository controls:**

- GitHub secret-scanning workflow present.
- Backend example configuration no longer contains a nonempty reporting key in the inspected revision.
- The project owner reported a successful scan without detected leaks.

### Assumed / owner-reported

- Every applicable deployed environment has been updated.
- No other live service uses the previous key.
- No unauthorized access occurred during the exposure window.

These are not independently established by the local authentication test.

### Tests

Required regression checks:

- Invalid bearer token returns HTTP 401.
- Missing bearer token returns HTTP 401 when reporting is configured.
- Valid bearer token is accepted.
- Missing or insufficiently configured server key returns HTTP 503.
- Admin reports do not expose secrets.
- CI detects tracked real environment files.
- CI detects a hardcoded reporting key in the example file.
- GitHub scanning detects representative fake test credentials.
- Future cross-process politeness tests validate global host concurrency, spacing, and Retry-After backoff.

### Commits

**Exposure:**

`5752803e81edc07f33e6f183d88dda3100cc7000`

**Incident documentation / verification-script exclusion:**

`98daf6c0ca644fd46de0845f68e88876cbcd1c32`

The latter does not contain the live key rotation, which was performed through local environment configuration.

## Revisit when

- A second credential exposure occurs.
- An additional production environment or administrative consumer is introduced.
- Manual key rotation becomes operationally difficult.
- GitHub secret scanning produces repeated unreviewed failures.
- The project introduces automated deployment credentials.
- The crawler is formally scaled to multiple hosts or processes.
- Requests receive repeated HTTP 429 responses or host-level backoff becomes inconsistent across crawler processes.
- A shared politeness service is implemented and its distributed correctness is tested.

## Rules for future changes

- Do not commit valid credentials.
- Do not hardcode secrets in configuration examples.
- Do not consider deleting a committed secret equivalent to revocation.
- Do not disable secret scanning to bypass legitimate findings.
- Do not place administrative bearer tokens in frontend browser bundles.
- Do not change the authentication boundary without reviewing ADR-0032.
- Do not claim cross-process host politeness while its state is process-local.
- Before editing, inspect the environment-loading configuration, admin authentication dependency, GitHub Actions workflow, and affected deployment settings.
- Regression tests that must keep passing: invalid-token rejection, valid-token acceptance, tracked-env-file detection, and secret-scanning checks.