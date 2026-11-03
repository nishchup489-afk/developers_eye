---
id: INC-0005
title: Pinned transport accepted any path, Host header or TLS server name on an approved origin
status: resolved
date: 2026-10-20
severity: high
area: crawler
feature: url-safety
code:
  - crawler/src/crawler/fetcher/transport.py:PinnedAsyncTransport.handle_async_request
  - crawler/src/crawler/policy_and_politeness/policy_coordinator.py
  - crawler/src/crawler/fetcher/errors.py:FetcherSecurityError
fix_commits: [8a91e50]
related: [ADR-0007]
---

# INC-0005: Pinned transport accepted unchecked URLs on an approved origin

## Signature
No error; the request was sent. Three tests in `fetcher/tests/fetcher_tests/tests/test_fetcher.py` were marked as expected failures (`xfail`) for these cases before the fix.

## Summary
ADR-0007 relies on the rule "only the exact URL that passed the coordinator's checks may be requested". The fetcher's `PinnedAsyncTransport` only compared the **origin** (scheme, host, port). A client built for an approved `https://docs.example.org/docs` would also send `https://docs.example.org/admin`, a different query string, a request with a custom `Host:` header (to reach another virtual host on the same IP), or a request with a TLS `sni_hostname` override. None of those had passed the robots or scope checks for their path.

A second bug was found in the same review: `policy_coordinator.py` imported `FetcherSecurityError` and then defined its own class with the same name, so security rejections raised by the real fetcher were not caught. A rejected response could be treated as an ordinary retryable failure (`DEFER`) instead of `DENY`.

No exploit was seen. The crawler only builds one client per approved URL and does not reuse it, so in practice the unchecked requests could only happen through a code change. That is why the fix matters: the transport is the last line of defense.

> **Question for nish:** were these found by a review pass of your own (the commit is "all improvement reviewed") or by an automated reviewer? Worth saying, so the next person knows how this kind of gap was caught.

## Expected vs actual
- Expected: the transport refuses any request that is not byte-for-byte the approved URL with the approved `Host` and default SNI.
- Actual: any path or query on the approved origin was accepted, as were custom `Host` headers and SNI overrides. Fetcher security errors could be retried instead of denied.

## Root cause
The transport was written to stop connections to other hosts (DNS pinning), and "same origin" was treated as enough. Robots and path scope are per URL, not per origin. The coordinator's duplicate exception class shadowed the real one, so `except FetcherSecurityError` caught nothing the fetcher raised.

## Fixes that did not work
None recorded. The tests for the three transport cases existed as `xfail` before the fix.

## Resolution
In `8a91e50`:
- `PinnedAsyncTransport.handle_async_request()` now rejects, with `FetcherSecurityError`: any method other than `GET`; a scheme or port different from the approved one; `request.url != expected_url` ("A different URL requires fresh policy checks"); a `Host` header that differs from the approved authority; any `sni_hostname` extension.
- `policy_coordinator.py` imports `FetcherSecurityError` from `fetcher/errors.py` and no longer defines its own. Page fetches turn it into `DENY`; robots retrieval turns it into `DEFER`.

## Prevention
- Regression tests: the three former `xfail` tests now pass normally, plus a query-change case (`fetcher/tests/fetcher_tests/tests/test_fetcher.py`); coordinator tests raise the fetcher's real exception and assert class identity (`policy_and_politeness/tests/test_policy_coordinator.py`).
- Remaining risk: `policy_and_politeness/dns_policy.py:PinnedHTTPTransport` is a second, separate implementation with similar checks (no `GET`-only rule). It is only used by tests today (ADR-0007).

## Rules for future changes
- The transport must compare the full URL, not just the origin.
- Never define a second exception class with the name of one you import; import the shared one from `fetcher/errors.py`.
- Security rejections from the fetcher are `DENY`, never retried.
- Keep passing: `fetcher/tests/fetcher_tests/tests/test_fetcher.py`, `policy_and_politeness/tests/test_policy_coordinator.py`.

## References
- `0_tech_docs/journal/update-log/02_policy_rejections.md`, `03_pinned_requests.md`
