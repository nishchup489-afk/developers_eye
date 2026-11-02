# URL safety and pinned transport

Area: crawler · Status: active

## Purpose

Approves hosts, resolves and rejects unsafe destinations, pins approved IPs and checks each redirect. Shared exception identity and exact URL/Host/TLS validation are security boundaries.

Reviewed against `facd333` on 2026-11-02. “Active” means implementation exists, not that it is integrated into every caller or production-verified.

## Code

- [`crawler/src/crawler/policy_and_politeness`](../../../crawler/src/crawler/policy_and_politeness)
- [`crawler/src/crawler/fetcher/transport.py`](../../../crawler/src/crawler/fetcher/transport.py)

## How-it-works docs

- [`crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md`](../../../crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md)
- [`crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md`](../../../crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md)

## Records

| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0007](ADR-0007-fail-closed-ssrf-checks-with-ip-pinning.md) | decision | Every request hop passes an exact host allowlist, then public-only DNS pinned into the transport | accepted |
| [INC-0005](INC-0005-pinned-transport-accepted-unchecked-urls.md) | incident | Pinned transport accepted any path, Host header or TLS server name on an approved origin | resolved |

## Decisions to record

The identified decisions for this feature are indexed above. Record new decisions or changed trade-offs before altering their invariants.

## Rules for future changes

- Never create an HTTP client for crawling outside `PolicyCoordinator` → `HTTPXHopFetcher` → `create_pinned_client()`; never enable `follow_redirects` (ADR-0007).
- Allowlist before DNS, DNS before any request, on every hop (ADR-0007).
- Reject the whole DNS answer if any address is not public (ADR-0007).
- Unsafe destinations are `DENY`, never `DEFER` (ADR-0007).
- The transport compares the full URL, `Host` and SNI, not just the origin; import `FetcherSecurityError` from `fetcher/errors.py`, never redefine it (INC-0005).
- Keep passing: `test_host_policy.py`, `test_redirect_policy.py`, `test_policy_coordinator.py`; run `test_dns_policy.py` after changing `dns_policy.py`.
