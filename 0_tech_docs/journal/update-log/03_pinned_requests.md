# Fixing pinned HTTP request validation

**Files involved:** `fetcher/transport.py` and `fetcher/tests/fetcher_tests/tests/test_fetcher.py`.

## The problem

The transport checked only the origin. It accepted a different path or query on that host, a custom HTTP Host header, and a TLS server-name override. Those requests had not passed the coordinator's original URL checks.

## What changed

Require the exact approved URL and its Host authority. Reject a custom TLS server-name extension before passing the request to httpcore.

Before: approval for `/docs` could be reused for `/admin`.

After: another path or query requires another policy check.

## Verification

The three previously expected-failing guard tests are now normal passing regression tests. A query-change case is covered too.
