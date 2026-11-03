---
id: ADR-0007
title: Every request hop passes an exact host allowlist, then public-only DNS pinned into the transport
status: accepted
date: 2026-10-31
area: crawler
feature: url-safety
code:
  - crawler/src/crawler/policy_and_politeness/host_policy.py:is_allowed_host
  - crawler/src/crawler/policy_and_politeness/dns_policy.py:is_public_ip
  - crawler/src/crawler/policy_and_politeness/dns_policy.py:validate_dns_results
  - crawler/src/crawler/fetcher/transport.py:PinnedAsyncTransport
  - crawler/src/crawler/fetcher/client.py:create_pinned_client
  - crawler/src/crawler/policy_and_politeness/redirect_policy.py:RedirectTracker
  - crawler/src/crawler/policy_and_politeness/policy_coordinator.py:PolicyCoordinator.fetch
  - crawler/src/crawler/fetcher/fetch.py:HTTPXHopFetcher
supersedes:
superseded_by:
related: [ADR-0006]
---

# ADR-0007: Exact host allowlist, then public-only DNS pinned into the transport, on every hop

## TL;DR
Before any byte is sent, a URL must (1) pass a cheap syntax and exact-hostname allowlist check against its source's `allowed_hosts`, then (2) resolve to addresses that are all public, and the HTTP connection is then forced to those exact addresses. Redirects are never followed by HTTPX; each `Location` is a new hop that runs the whole sequence again (allowlist, DNS, robots, politeness). Anything unsafe is a `DENY` that is never retried. This blocks SSRF to private networks and cloud metadata, including through redirects and DNS rebinding.

## Context
The crawler fetches URLs it did not choose: links found in pages, sitemap entries, feed items, JSON API records, and redirect targets. Any of them can point at `http://169.254.169.254/` (cloud metadata), `localhost`, a LAN address, or a public hostname whose DNS answer is a private IP. The crawler runs on the developer's machine today and may run in the cloud later, where metadata endpoints hand out credentials.

A plain "resolve, check the IP, then let HTTPX connect" has a time-of-check to time-of-use gap: HTTPX resolves the name again when it connects, and a hostile DNS server can answer with a public IP the first time and `127.0.0.1` the second (DNS rebinding). Automatic redirects have the same problem: the check runs on the first URL, and HTTPX then connects wherever `Location` says.

> **Question for nish:** was there a specific trigger for building this before most of the crawler (it landed 2026-10-12, before the worker existed): something you read, a CTF, or a security checklist? A line on that helps explain why the bar is this high for a hobby-scale crawler.

## Decision
Order of checks per hop in `PolicyCoordinator.fetch()`:

1. **Syntax and allowlist** (`is_allowed_host`, no network): reject whitespace, control characters and backslashes; scheme `http` or `https` only; no user or password in the URL; a valid normalized hostname (IDNA, lowercase, no trailing dot); port empty or the scheme default (80/443); a trailing `:` is malformed; the hostname must **exactly** equal one of the source's `allowed_hosts` (no suffix or wildcard matching).
2. **DNS** (`resolve_safe_destination`): resolve A and AAAA with a 5 s timeout. Every address must pass `is_public_ip()`: `ip.is_global`, not multicast, not reserved, no scope id; IPv4-mapped IPv6 is unwrapped and checked as IPv4; 6to4 and Teredo are rejected. **If any address is unsafe, the whole answer is rejected.** IP literals skip DNS but get the same check.
3. **Robots and politeness** for that origin (see `robots-and-politeness`).
4. **Pinned request** (`HTTPXHopFetcher` → `create_pinned_client` → `fetcher/transport.py:PinnedAsyncTransport`): a new client and connection pool per request (`trust_env=False`, `follow_redirects=False`, `max_redirects=0`, HTTP/1.1). Its network backend only connects to the approved IPs for that host and port, falling back only to other approved IPs, and refuses a custom local bind address and Unix sockets. The transport refuses anything but `GET`, a URL that is not exactly the approved URL, a different scheme or port, a custom TLS SNI, or a `Host` header that differs. TLS verifies the certificate against the hostname as normal.
5. **Redirects** (`RedirectTracker`): HTTPX automatic redirects are off. On 301/302/303/307/308 the tracker resolves `Location` against the current URL, rejects non-HTTP(S) or malformed schemes, refuses HTTPS → HTTP downgrade, stops after 5 redirects, and the loop goes back to step 1 for the new URL.
6. **Outcomes.** Allowlist failure, unsafe DNS, redirect rejection, oversize response and fetcher security errors are `DENY` (target `blocked`, never retried). DNS lookup failure and network errors are `DEFER` (retry with backoff, ADR-0006).

The final URL is checked again in the job: a 200 whose final URL is outside the source's hosts or path scope is `block`ed.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Allowlist, then all-public DNS, pinned transport, manual redirects re-checked per hop | Closes rebinding and redirect escapes; cheap checks first; no extra service | A custom HTTPX transport to maintain; a new connection per hop | chosen |
| B. Resolve and check the IP, then let HTTPX connect normally | Simple | DNS rebinding between check and connect | rejected |
| C. Let HTTPX follow redirects, check only the first URL | Simple | Redirect to `http://127.0.0.1/` or another host bypasses every check | rejected |
| D. Run the crawler behind an egress proxy or firewall that blocks private ranges | Defense outside the code | Not available on a dev laptop; still need app checks for host scope | not instead of A; good later in addition |
| E. Accept the DNS answer if at least one address is public, and use only those | Fewer false rejections | A host that resolves to both public and private addresses is suspicious; silently picking is easy to get wrong | rejected (fail closed) |
| F. Suffix or wildcard host matching (`*.python.org`) | Fewer allowlist entries | One subdomain takeover or user-content subdomain widens scope | rejected |

## Why
- **Security.** Each check closes a known bypass: exact host match stops scope creep; checking every DNS address and pinning the connection stops rebinding; re-running the checks on every redirect stops redirect escapes; refusing custom `Host` and SNI stops virtual-host tricks over an approved IP.
- **Cost order.** The allowlist needs no network, so most bad URLs are rejected before a DNS query.
- **Retry behaviour.** Separating `DENY` (unsafe, permanent) from `DEFER` (DNS outage, network error) means an attacker cannot make the crawler keep retrying an unsafe target, while a real outage still recovers.

## Consequences
- Gained: the crawler can safely follow untrusted links, feeds and redirects.
- Accepted limitations:
  - Non-default ports are never crawled (`:8080` fails the allowlist).
  - Every subdomain must be listed explicitly in `allowed_hosts`.
  - A host whose DNS includes any non-public address is blocked even if its main address is public.
  - No connection reuse between hops or requests, so each request pays DNS, TCP and TLS setup.
  - Cross-host redirects are only followed if the new host is also in `allowed_hosts`.
  - HTTP proxies are not supported.
- Two pinned transports exist: `fetcher/transport.py:PinnedAsyncTransport` (used for every crawl request) and `policy_and_politeness/dns_policy.py:PinnedHTTPTransport` / `safe_http_transport()` (same idea, only used by `test_dns_policy.py`). A fix to one does not reach the other.

  > **Question for nish:** is `dns_policy.PinnedHTTPTransport` meant to be removed now that the fetcher has its own, or kept as the reference implementation?
- What depends on this: the fetcher (`HTTPXHopFetcher`) must build its client with `create_pinned_client()` for every request, and the job's final-URL scope check relies on `redirect_chain` from this loop.

## Invariants
- No HTTP request is sent unless its exact URL passed `is_allowed_host()` and its host resolved to an all-public address set in the same hop.
- The TCP connection goes only to an address from that approved set.
- HTTPX automatic redirects stay disabled; each redirect is a new hop through the coordinator.
- Unsafe destinations are `DENY`, never `DEFER`.
- HTTPS never redirects to HTTP unless `allow_https_downgrade` is explicitly set (it is not, anywhere).

## Failure modes
- DNS resolver outage: every URL `DEFER`s and backs off; nothing is fetched until DNS works.
- A legitimate site with an IPv6 address in a reserved range: blocked; add nothing, it fails closed.
- The allowlist and DNS check are skipped if new code creates an `httpx.AsyncClient` directly. That is the main way to break this design.

## Evidence
- Tests: `policy_and_politeness/tests/test_host_policy.py`, `test_dns_policy.py` (own runner, needs network), `test_redirect_policy.py`, `test_policy_coordinator.py`; case list in `tests/test_case.md`.
- Measured: none (no latency cost measured for per-hop DNS and no keep-alive).
- Incidents: `0_tech_docs/journal/update-log/02_policy_rejections.md`, `03_pinned_requests.md`.
- Commits: `3a84cd7` (host and DNS policy), `cf39613` (redirect policy).
- How-it-works: `crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md`, `2_dns_policy.md`, `5_redirect_policy.md`, `6_policy_coordinator.md`.

## Revisit when
- The crawler runs in a cloud environment: add an egress firewall rule for private ranges and metadata as a second layer (option D).
- Connection setup time shows up as a large share of fetch time; consider a per-host pinned pool reused across requests to the same host and IP set.
- A source needs a non-default port or wildcard subdomains; that needs a new ADR.

## Rules for future changes
- Never create an HTTP client for crawling outside `PolicyCoordinator` → `HTTPXHopFetcher` → `create_pinned_client()`.
- Never enable `follow_redirects` on a crawling client.
- Keep the allowlist check before DNS, and DNS before any request.
- Keep "reject the whole DNS answer if any address is unsafe".
- Do not turn a `DENY` into `DEFER` to "be lenient"; unsafe targets must not be retried.
- Keep passing: `test_host_policy.py`, `test_redirect_policy.py`, `test_policy_coordinator.py`, and run `test_dns_policy.py` after any change to `dns_policy.py`.
