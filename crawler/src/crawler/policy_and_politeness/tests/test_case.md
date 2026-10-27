# Policy and politeness test cases

Tests for host allowlisting, DNS/IP safety, robots.txt rules and caching, redirects, per-host politeness, and the `PolicyCoordinator` that ties them together.

Some files are pytest/unittest suites; others (`test_host_policy.py`, `test_dns_policy.py`, `test_robots_policy.py`) are Colorama scripts with their own `main()` runner and are meant to be run directly with `python -m ...`.

## test_host_policy.py

Script runner (`main()`) over a table of cases for `host_policy`. No network.

| Group | What it checks |
| --- | --- |
| Suspicious-character detection (`has_suspicious_characters`) | A normal URL is clean. Backslash, raw space, tab, newline, NUL, zero-width space, and bidi override are flagged. A percent-encoded space (`%20`) is not flagged. |
| Hostname normalization (`normalize_hostname`) | Lowercases, strips one trailing root dot, converts IDN to punycode (`bücher.de` to `xn--bcher-kva.de`), keeps IPv4, compresses IPv6. Returns `None` for empty, `.`, leading/trailing hyphen, underscore, empty label, label over 63 chars, hostname over 253 chars, and embedded whitespace. |
| Allowed-host URL validation (`is_allowed_host`) | Accepts http/https on the allowlisted host regardless of case, trailing dot, default ports, IDNA, and IPv6 allowlist entries; allowlist entries are normalized too. Rejects `ftp:`/`file:`/missing scheme, empty or non-string input, missing host, unrelated hosts, deceptive suffixes (`docs.python.org.evil.example`), unlisted subdomains, any userinfo (including `docs.python.org@evil.example`), non-default/wrong/alphabetic/out-of-range/empty ports, malformed IPv6 brackets, backslash, newline, zero-width characters, and an empty allowlist. Invalid allowlist entries are ignored rather than failing. |

## test_dns_policy.py

Script runner (`main()`) for `dns_policy`. DNS (`getaddrinfo`) and the HTTP core are mocked, so no real network or database is used.

| Section | What it checks |
| --- | --- |
| IP address safety (`is_public_ip`) | Public IPv4/IPv6 and IPv4-mapped public IPv6 are allowed. Private (10/8, 172.16/12, 192.168/16), loopback, link-local/cloud metadata (169.254.169.254), CGNAT (100.64/10), unspecified, multicast, broadcast, documentation, benchmarking, IPv6 ULA/link-local/documentation/multicast, IPv4-mapped private/loopback, 6to4, Teredo, scoped IPv6, invalid strings, hostnames, empty, and `None` are rejected. |
| DNS result validation (`validate_dns_results`) | Public results are returned, deduplicated, and IPv6 is normalized. An empty answer, or any private, loopback, invalid, multicast, or metadata address in the set, raises `UnsafeDestinationError`. |
| Hostname resolution (`resolve_hostname`) | Normalizes the hostname before lookup, dedupes A/AAAA results, skips DNS for IP literals, returns `[]` for an empty answer, turns `gaierror` and timeouts into `DNSResolutionError`, rejects malformed hostnames, and rejects a timeout of `0` or less with `ValueError`. |
| Combined DNS safety (`resolve_safe_destination`) | All-public results pass; one unsafe address rejects the whole result; an empty answer is rejected; DNS failures propagate. |
| Transport construction (`safe_http_transport`) | A valid origin with approved IPs builds a transport pinned to that host, port 443, and IPs. Private, loopback, mixed, or empty IP lists, embedded credentials, a non-standard HTTPS port, and `ftp:` raise `UnsafeDestinationError`. |
| HTTPX request security | An approved request reaches the core with the original Host header and path. Requests to another host, a different path or query on the same host, a different scheme, a custom `Host` header, or a custom TLS SNI are blocked before the network. A redirect to another host is blocked and no second request is sent. |
| Pinned TCP connections | Connects only to the approved numeric IP, falls back to the next approved IP on failure, fails closed when all fail, refuses a wrong hostname or port before opening a socket, and refuses Unix domain sockets. |

## test_robots_rules.py

Pytest unit tests for robots.txt matching in `robots_policy`.

| Test | What it checks |
| --- | --- |
| `test_path_matching` (parametrized, 21 cases) | `*` wildcards and `$` end anchors (query strings defeat `$`), longest match wins between Allow/Disallow, Allow wins on equal length, empty `Disallow:` allows all, paths are case-sensitive, percent-encoding is compared after decoding unreserved characters and UTF-8, but `%2F` is not treated as `/`, encoded `%2A`/`%24` are literal `*`/`$`, wildcards in query patterns, multi-wildcard patterns, `/robots.txt` is always allowed, and inline `#` comments are stripped. |
| `test_merge_repeated_matching_groups` | Two separate groups for the same user agent are merged. |
| `test_specific_group_replaces_wildcard_case_insensitively` | A group naming `developerseyebot` (any case) replaces the `*` group for `DevelopersEyeBot/1.0`. |
| `test_multiple_agents_and_other_records_do_not_end_group` | A BOM, multiple `User-agent` lines, and a `Sitemap` line do not break the group; `/private` is still disallowed. |
| `test_empty_specific_group_allows_without_wildcard_fallback` | An empty bot-specific group allows everything and does not fall back to the `*` group's `Disallow: /`. |
| `test_nontext_rejected` | `parse_robots(None)` raises `TypeError`. |

## test_robots_policy.py

Script runner (`main()`) that uses a real PostgreSQL session (rolled back at the end) and a `FakeFetcher` so no robots.txt is fetched over the network. Do not run against production.

| Section | What it checks |
| --- | --- |
| Origin and robots URL | `get_robots_origin` strips path, query, fragment, and default port. `get_robots_url` points to `/robots.txt` at the site root, keeps the scheme and non-default ports, and rejects `file:` URLs. |
| Parsing and permissions | Bot-specific Allow/Disallow rules apply, `*` rules apply to other bots, an empty file allows everything, and non-text input raises `TypeError`. |
| `robots_cache` operations | A missing origin returns `None`. Saving stores status and raw text with timezone-aware timestamps and a positive TTL. Saving again upserts (no duplicate rows). An expired row is treated as a miss. |
| Coordinator ALLOW/DENY and cache reuse | A 200 with a permitted path gives `ALLOW` and fetches only the origin's `robots.txt`. A second evaluation uses the fresh cache (no fetch) and returns `DENY` for a disallowed path. |
| HTTP status and failures | 404 means `ALLOW` and is cached (no refetch). 403 gives `DENY`. 503 gives `DEFER` with the default delay and is not cached. 429 gives `DEFER` with the supplied retry delay. A fetch error, an unhandled 302, an oversized body (not cached), and a non-text body all give `DEFER`. |
| Validation | `javascript:` URLs, an empty user agent, a non-positive cache TTL in `save_robots_cache`, and a `cache_ttl_seconds=0` in `evaluate_robots_policy` all raise `ValueError`. |

## test_redirect_policy.py

Pure pytest unit tests for `redirect_policy`.

| Test | What it checks |
| --- | --- |
| `test_supported_redirect_status` / `test_non_redirect_status` | Only 301, 302, 303, 307, and 308 count as redirects; 200, 204, 300, 304, 305, 306, 3070, 4xx, and 5xx do not. |
| `test_resolve_location_header` | Absolute-path, `../`, relative, query-only, fragment-only, protocol-relative, and absolute `Location` values are resolved against the current URL, with fragments removed. |
| `test_url_normalization` / `test_query_string_preserved` | Scheme and host are lowercased, the default port and fragment are dropped, path case and the query are kept. |
| `test_reject_unsafe_absolute_urls` | Empty, host-less, `ftp:`, `file:`, credentialed, bad/zero/out-of-range/empty ports, malformed or scoped IPv6, whitespace, newlines, and backslash tricks raise `InvalidRedirectError`. |
| `test_reject_invalid_location_header` | A missing, empty, `javascript:`, `data:`, `ftp:`, malformed-scheme, credentialed, bad-port, whitespace, newline, or backslash `Location` raises `InvalidRedirectError`. |
| `test_default_limit_is_five_hops` | The default limit is 5; the sixth hop raises `RedirectLimitError` and the tracker stays on hop 5. |
| `test_custom_redirect_limit` / `test_zero_redirect_limit` | `max_redirects=1` allows one hop; `max_redirects=0` allows none. |
| `test_self_redirect_is_loop` / `test_fragment_cannot_hide_redirect_loop` / `test_multi_hop_redirect_loop` | Redirecting to the start URL (even with a different fragment) or back to an earlier hop raises `RedirectLoopError` without changing state. |
| `test_https_to_http_downgrade_rejected` / `test_explicitly_allow_https_downgrade` / `test_http_to_https_upgrade_is_allowed` | HTTPS to HTTP raises `RedirectDowngradeError` unless `allow_https_downgrade=True`; HTTP to HTTPS is always allowed. |
| `test_https_to_https_cross_host_is_syntactically_allowed` | Cross-host redirects pass here; host permission is the coordinator's job. |
| `test_private_ip_is_not_rejected_by_syntax_validation` | A `127.0.0.1` destination passes here; the DNS/IP policy rejects it. |
| `test_non_redirect_status_does_not_change_tracker_state` / `test_bad_location_does_not_change_tracker_state` | Errors leave `redirect_count` and `current_url` unchanged. |
| `test_invalid_max_redirects` / `test_invalid_https_downgrade_setting` | Negative, float, bool, or `None` limits, and non-bool downgrade settings, raise `ValueError`. |
| `test_trackers_are_independent` | Two trackers do not share state. |

## test_politeness_policy.py

Unittest suite for `politeness_policy`.

| Class | What it checks |
| --- | --- |
| `TestHostKey` | `get_host_key` returns the hostname, gives the same key across paths, schemes, and ports, raises `ValueError` for non-URLs, relative paths, and `ftp:`, and `TypeError` for `None`. |
| `TestRetryAfter` | `parse_retry_after` handles seconds, surrounding whitespace, `0`, a missing header (`None`), an invalid value (`None`), a future HTTP date (about 120 s), a past date (`0`), and caps a huge number at `MAX_BACKOFF_SECONDS`. |
| `TestConfiguration` | Defaults are 2 concurrent per host, 2.0 s interval, 60 s backoff. Custom values are kept. Zero, negative, bool, or float concurrency, negative or NaN interval, infinite backoff, and non-positive max backoff raise `ValueError`. |
| `TestPolitenessManager` (async) | Host state is created on acquire, reused for the same host, and separate per host. Two slots per host are granted, a third waits until one is released, peak concurrency never exceeds the limit across 10 workers, and different hosts do not block each other. The minimum interval is enforced and `0` means no wait. `apply_backoff` delays the next acquire, never shortens an existing backoff, is capped at the max, and rejects negative, NaN, infinite, or bool values. `record_response` sets a backoff for 429 and 503, does nothing for 200, and falls back to the default backoff for an invalid `Retry-After`. Releasing an unknown host or releasing twice raises `ValueError`. `polite_slot` releases on exceptions, and cancelling a waiting acquire releases its slot. |

## test_policy_coordinator.py

Pytest suite for `PolicyCoordinator` with a `FakeOneHopFetcher`, and with `resolve_safe_destination` and `evaluate_robots_policy` monkeypatched. No live HTTP, DNS, or database.

| Test | What it checks |
| --- | --- |
| `test_coordinator_uses_fetchers_security_exception` | The coordinator uses the fetcher's `FetcherSecurityError` class. |
| `test_success_approved_ips_forwarded_to_fetcher` | A normal fetch returns `ALLOW`, status, body, and a one-entry redirect chain, and passes the approved IPs, 2,000,000-byte limit, 15 s timeout, and `DevelopersEyeBot` user agent to the fetcher. |
| `test_bad_urls_never_get_dns_or_network` | `ftp:`, spaces, unlisted hosts, port 0, and credentials give `DENY` without DNS or fetch. |
| `test_private_ip_blocked_before_fetch` | An unsafe DNS result gives `DENY` before robots or fetch. |
| `test_dns_failure_deferred` | A DNS failure gives `DEFER` with the default delay. |
| `test_robots_blocks_network` | A robots `DENY` or `DEFER` is returned with its retry delay and nothing is fetched. |
| `test_redirect_rechecks_host_dns_and_robots` | Following a redirect re-runs DNS and robots for the new host and records both URLs in the chain. A mixed-case `Location` header is accepted. |
| `test_unapproved_redirect_stops_before_second_request` / `test_redirect_into_private_address_stops` | A redirect to an unlisted host, or to a host that resolves to a private IP, gives `DENY` after one request. |
| `test_missing_location_loop_and_https_downgrade` | A missing `Location`, a self-redirect, or an HTTPS to HTTP redirect gives `DENY` with status 302 after one request. |
| `test_redirect_hop_limit` | With `max_redirects=2`, the third redirect gives `DENY` after three requests. |
| `test_rate_limit_defer_records_backoff` | 429 and 503 give `DEFER` with the `Retry-After` value (case-insensitive header) and set a host backoff. |
| `test_status_outcome` | 500 and 502 give `DEFER`; 404 gives `ALLOW`. |
| `test_network_error_deferred` | A connect timeout gives `DEFER`. |
| `test_security_or_size_error_denied_and_slot_freed` / `test_body_limit_catches_fake_fetcher_mistake` | `ResponseTooLargeError`, `FetcherSecurityError`, or a body over `max_body_bytes` gives `DENY` and the politeness slot is released. |
| `test_robots_fetch_bootstrap_without_self_recursion` | `_fetch_robots` fetches robots.txt with DNS but without calling the robots policy again, using `MAX_ROBOTS_BYTES`. |
| `test_robots_redirect_rechecks_dns_and_host` | A robots.txt redirect re-resolves DNS for the new host. |
| `test_robots_fetch_failure_becomes_robots_error` | A connect error while fetching robots raises `RobotsFetchError`. |
| `test_request_cancellation_frees_slot` | Cancelling an in-flight fetch releases the politeness slot. |
| `test_two_hosts_have_distinct_slots` | With concurrency 1, two different hosts can fetch at the same time. |
| `test_invalid_max_redirects_rejected` / `test_invalid_max_body_bytes_rejected` | Negative, bool, or float `max_redirects`, and zero, negative, bool, or float `max_body_bytes`, raise `ValueError`. |
