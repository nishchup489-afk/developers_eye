---
id: INC-0045
title: Frontend CI stopped at the picomatch dependency audit
status: resolved
date: 2026-11-17
severity: medium
area: infra
feature: local-dev-and-testing
code: [frontend/package.json, frontend/package-lock.json, .github/workflows/ci.yml]
fix_commits: []
related: []
---

# INC-0045: Frontend CI stopped at the picomatch dependency audit

## Signature

```text
picomatch vulnerable to ReDoS through single-branch repeated extglobs
6 high severity vulnerabilities
Error: Process completed with exit code 1.
```

## Summary

The frontend job on `main` stopped after `npm ci` succeeded. The
`npm audit --omit=dev --audit-level=high` step reported six high-severity
entries and exited with code 1. GitHub skipped lint, type checking, the
production build, and frontend tests for that run.
[Failed job](https://github.com/nishchup489-afk/developers_eye/actions/runs/44190941573/job/134419841107) ·
[Tracking issue](https://github.com/nishchup489-afk/developers_eye/issues/32)

## Expected vs actual

- Expected. The locked frontend dependencies pass the production audit and CI
  runs the remaining checks.
- Actual. The audit stopped the job before the application checks started.

## Root cause

The production dependency tree resolved two copies of `picomatch@4.0.7`.
`fumadocs-mdx` depends on one directly. `tinyglobby`, which Fumadocs uses to
discover documentation files, depends on the other and shares it with
`fdir`. The audit counts the affected package and five packages that depend on
it. All six entries trace to
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
The affected document discovery runs during the build. The handbook serves
compiled documents, and its search route accepts search text.

## Resolution

Pin the provenance-attested
[`@ryotsu/picomatch@4.0.7-a` backport](https://github.com/ryotsu-kankichi/secured-picomatch)
under the `fumadocs-mdx` and `tinyglobby` dependency paths. The package diff
against upstream 4.0.7 shows the parser guard that collapses repeated wildcard
branches when equivalent and treats other risky branches as literals. The
lockfile pins the reviewed tarball by integrity. Upstream had no patched
release at the time of the incident. The audit's suggested forced fix would
downgrade Fumadocs MDX across major versions.

## Prevention

- Run `npm ci` and `npm audit --omit=dev --audit-level=high` from
  `frontend/` when changing the lockfile. CI enforces the same audit.
- Verify the production build, handbook routes, and document search when
  changing the documentation matcher.
- Replace the backport with an upstream release that addresses the advisory
  once one is available. The existing development-only ESLint dependency uses
  a separate `picomatch@2.3.2` copy outside the production audit.

## Rules for future changes

- Verify the production audit and handbook route and search behavior when
  replacing the temporary matcher overrides (INC-0045).
