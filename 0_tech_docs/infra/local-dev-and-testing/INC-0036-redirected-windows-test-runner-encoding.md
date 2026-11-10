---
id: INC-0036
title: Redirected Windows test runner failed before executing suites
status: resolved
date: 2026-11-09
severity: medium
area: infra
feature: local-dev-and-testing
code: [scripts/run_all_tests.py]
fix_commits: []
related: [ADR-0051]
---

# INC-0036: Redirected Windows test runner failed before executing suites

## Signature

`UnicodeEncodeError: 'charmap' codec can't encode character '\u2714'`

## Summary

Redirecting the full validation run to a log on Windows selected cp1252 for
stdout. Rich's environment table printed a check mark and the runner exited
before running any suite.

## Expected vs actual

- Expected: redirected diagnostics and saved reports work like terminal output.
- Actual: environment rendering raised before the backend suite started.

## Root cause

The runner decoded subprocess output as UTF-8 but did not configure its own
redirected stdout/stderr. Windows pipe encoding could not represent its symbols.

## Resolution

Configure reconfigurable stdout/stderr streams as UTF-8 at entry to `main`, with
backslash replacement for otherwise unencodable data. Embedded streams without
`reconfigure` remain supported.

## Prevention

- Regression: reran the full runner redirected to `tests/reports/checklist-baseline.log`;
  it reached every suite and saved HTML/text/JSON reports.
- That baseline exposed separate stale test-schema failures. It is not recorded
  as a passing system run.

## Rules for future changes

- Keep console output, subprocess decoding, and saved diagnostics UTF-8 compatible.
- Validate redirected execution when changing diagnostic symbols or rendering.
