# URL safety (SSRF, DNS, redirects)

Area: crawler · Status: active

## Purpose
Decides whether a URL may be requested at all: exact host allowlist, public-only DNS with the connection pinned to the approved IPs, and a fresh check on every redirect hop. It protects the machine running the crawler from SSRF. It does not decide crawl scope by depth or path (`url-frontier`) or robots and rate limits (`robots-and-politeness`).

## Code
- `crawler/src/crawler/policy_and_politeness/host_policy.py`
- `crawler/src/crawler/policy_and_politeness/dns_policy.py`
- `crawler/src/crawler/policy_and_politeness/redirect_policy.py`
- `crawler/src/crawler/policy_and_politeness/policy_coordinator.py`
- `crawler/src/crawler/fetcher/transport.py`, `crawler/src/crawler/fetcher/client.py`

## How-it-works docs
- `crawler/src/crawler/policy_and_politeness/docs/`

## Records
| ID | Type | Title | Status |
| --- | --- | --- | --- |
| [ADR-0007](ADR-0007-fail-closed-ssrf-checks-with-ip-pinning.md) | decision | Exact host allowlist, then public-only DNS pinned into the transport, on every hop | accepted |

## Decisions to record
Found in `technical_handoff.md` and the code. Turn each into an ADR file in this folder, then tick it.

- [x] Two-stage URL validation: cheap allowlist first, then DNS (ADR-0007)
- [x] Block private IP ranges and pin resolved IPs against DNS rebinding (ADR-0007)
- [x] Re-check policy on every redirect hop (ADR-0007)

## Rules for future changes
- Never create an HTTP client for crawling outside `PolicyCoordinator` → `HTTPXHopFetcher` → `create_pinned_client()`; never enable `follow_redirects` (ADR-0007).
- Allowlist before DNS, DNS before any request, on every hop (ADR-0007).
- Reject the whole DNS answer if any address is not public (ADR-0007).
- Unsafe destinations are `DENY`, never `DEFER` (ADR-0007).
- Keep passing: `test_host_policy.py`, `test_redirect_policy.py`, `test_policy_coordinator.py`; run `test_dns_policy.py` after changing `dns_policy.py`.
