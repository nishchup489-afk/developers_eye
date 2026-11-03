# Crawler and indexer test cases

One file for every crawler and indexer test suite, grouped by module. Tests live under `crawler/tests/crawler/<module>/`, `crawler/tests/indexer/` and `crawler/tests/benchmarks/`. How to run them is in [README.md](README.md).

## ingestion

### Crawler ingestion test cases

Offline tests for structured-resource ingestion: XML sitemaps, RSS/Atom feeds, and JSON APIs, plus how the worker dispatches them. They use literal XML/JSON and test doubles for network and persistence, but the worker tests still run the real parser and processor. See `README.md` in this folder for how to run them and the database suites.

#### test_sitemap.py

`parse_sitemap` unit tests. No network or PostgreSQL.

| Test | What it checks |
| --- | --- |
| `test_namespaced_urlset` | A namespaced `<urlset>` returns page URLs in order with duplicates removed, and no sitemap URLs. |
| `test_sitemap_index` | A `<sitemapindex>` returns nested sitemap URLs and no page URLs. |
| `test_unsafe_urls_ignored` | A `file://` location is dropped; the safe one is kept. |
| `test_malformed_xml_rejected` | Broken XML raises `MalformedContentError`. |
| `test_entity_expansion_rejected` | A DOCTYPE with an entity definition is rejected (XXE / entity expansion protection). |
| `test_non_sitemap_root_rejected` | An `<rss>` root is rejected. |
| `test_entry_limit_counts_duplicates_and_invalid_entries` | With `MAX_ENTRIES = 2`, duplicate and invalid entries still count toward the limit, so 3 entries raise `Too many`. |
| `test_gzip_is_bounded_after_decompression` | Gzipped sitemaps are decompressed and parsed, and a decompressed size over `MAX_XML_BYTES` raises `Decompressed ...`. |
| `test_invalid_documents_rejected` | Any DOCTYPE, an unrelated namespace, and truncated gzip are rejected. |
| `test_extension_namespace_does_not_supply_page_location` | An `<image:loc>` from an extension namespace is not treated as a page URL. |
| `test_corrupt_deflate_is_reported_as_malformed_xml` | Corrupt gzip data raises `MalformedContentError` mentioning gzip. |

#### test_sitemap_discovery.py

Sitemap seeding, robots.txt `Sitemap:` lines, scope, and worker dispatch, without live network or database writes.

| Test | What it checks |
| --- | --- |
| `test_seed_configuration_host_filter_and_default_sitemap` | `build_initial_targets` returns the base page, configured sitemaps on allowed hosts only (the `evil.test` one is dropped), and the default `/sitemap.xml`. `discover_sitemaps: False` leaves only the page. If the base URL is outside `allowed_path_prefixes`, the first target is a sitemap rather than the page. |
| `test_gzip_file_mime_types_are_only_enabled_for_sitemap_jobs` | `application/gzip` and `application/octet-stream` are allowed for sitemap fetches but not for page fetches. |
| `test_robots_declarations_are_absolute_bounded_and_case_insensitive` | `extract_robots_sitemaps` reads `Sitemap:` case-insensitively, strips comments, dedupes, drops relative and `file://` URLs, and caps the list at 100. A robots 200 decision carries the sitemap URLs. |
| `test_nested_maps_and_page_scope_have_separate_depth_meanings` | Page URLs from a sitemap are kept only if on an allowed host and path, and get depth 0 with `discovered_from_id` set. A nested sitemap index becomes a `sitemap` target at depth 0 but is dropped once the sitemap depth reaches `max_depth`. |
| `test_worker_sitemap_uses_policy_then_normal_finalization` | `process_job` for a sitemap target fetches through the policy coordinator once, stores no documents, and finalizes successfully with the in-scope page enqueued at depth 0. |

#### test_feeds.py

`parse_feed` unit tests for RSS and Atom.

| Test | What it checks |
| --- | --- |
| `test_rss_content_extensions_dates_and_invalid_records` | `content:encoded` is used as the body with `<script>` removed, `description` is kept, `dc:creator` becomes the author, `pubDate` is parsed to UTC, relative links are resolved, and `javascript:` links, non-URL GUIDs, and duplicate links are dropped (one document remains). |
| `test_atom_bases_text_html_xhtml_author_and_pagination` | Nested `xml:base` values resolve entry links, escaped titles are decoded, XHTML content is converted to text without scripts, the feed-level author is inherited, an entry with only a `urn:` ID is dropped, and `rel="next"` becomes an `rss` pagination link. |
| `test_bad_feeds_fail` | An empty `<rss/>`, an HTML root, truncated XML, any DOCTYPE, and empty input raise `MalformedContentError`. |
| `test_feed_limits_count_all_items` | `MAX_FEED_ENTRIES` counts every item (even empty ones) and raises `Too many`; `MAX_FEED_BYTES` raises `oversized`. |
| `test_bad_date_does_not_drop_valid_entry_and_guid_must_be_a_url` | An unparseable date leaves `published_at` as `None` but keeps the entry; a URL GUID is used as the link while an opaque GUID is dropped; `parse_record_date` returns `None` for an out-of-range year 1 date with an offset. |

#### test_json_api.py

`parse_json_api` unit tests.

| Test | What it checks |
| --- | --- |
| `test_default_array_single_object_and_items_container` | A top-level array, a single object, and an `{"items": [...]}` container all yield one document with resolved URL, author, UTC date, and `ingestion_format: json_api`. |
| `test_custom_nested_fields_html_and_body_pagination` | Custom `items_path`, `next_path`, and dotted field mappings (such as `user.login`) work, `body_format: html` strips tags and scripts, and the next page becomes an `api` link resolved against the request URL. |
| `test_invalid_entries_duplicate_urls_and_field_types` | Non-object entries and `javascript:` URLs are dropped, the first of duplicate URLs wins, and wrong-typed body and author become empty and `None`. |
| `test_missing_items_path_is_not_a_successful_empty_import` | A configured `items_path` that does not exist raises `MalformedContentError` instead of returning nothing. |
| `test_invalid_mapping_is_rejected` | Unknown option keys, `None` field mappings, unknown field names, a non-string `items_path`, an empty `next_path`, and an unsupported `body_format` raise `ValueError`. |
| `test_invalid_json_and_ambiguous_objects_are_rejected` | Duplicate keys, `NaN`, numbers that overflow to infinity, invalid JSON, and invalid UTF-8 raise `MalformedContentError`. |
| `test_json_limits_apply_before_filtering` | `MAX_JSON_ENTRIES` counts entries before filtering (`Too many`), and `MAX_JSON_BYTES` raises `oversized`. |
| `test_path_lookup_can_select_array_element_and_empty_collection_is_valid` | A numeric path segment (`data.0`) selects an array element, an empty collection is a valid empty import, and `items_path: ""` treats the root object as one item. |

#### test_ingestion_jobs.py

Runs `process_job` with the real parser and processor for `rss` and `api` targets, mocking the fetch, attempt start, checkpoints, and `_finalize`. The source limits content to `/docs` on `example.com`.

| Test | What it checks |
| --- | --- |
| `test_rss_worker_stores_only_in_scope_content_and_queues_pagination` (follow on/off) | Only the in-scope entry is stored (not `/private` or another host). The next feed page is always queued as `rss`; with `follow_entry_links` on, the entry link is also queued as a `page`. |
| `test_rss_http_directives_and_malformed_feed` | An `X-Robots-Tag: noindex, nofollow` header skips the document with reason `noindex` and queues no links. A malformed feed finalizes with action `retry` and `error_category: parse`. |
| `test_rss_source_queues_collection_outside_content_path` | An `rss` source seeds its feed URL as an `rss` target even though it is outside the `/docs` content path. |
| `test_json_worker_mapping_pagination_scope_and_processing` | A configured JSON mapping stores only the in-scope item and queues the next page as an `api` target at depth 1. |
| `test_json_noindex_nofollow_and_mapping_error_are_recorded` | `noindex, nofollow` headers skip the document and queue nothing; a missing `items_path` finalizes as `retry` with `error_category: parse`. |
| `test_json_source_uses_api_target_kind` | An `api` source seeds an `api` target. |
| `test_feed_does_not_expand_into_sitemaps_without_explicit_configuration` | Sitemap URLs from robots.txt are ignored for feed jobs unless `discover_sitemaps: True`, in which case a `sitemap` target is queued before the `rss` pagination target. |

## fetcher

### Developer's Eye fetcher tests

Copy both files from `tests/` into the repository's `crawler/tests/` directory. Run from `crawler/`:

```bash
poetry add --group dev pytest colorama
poetry run pytest tests/test_fetcher.py -q -s
```

The suite uses HTTPX MockTransport and fake HTTPCore network objects. It **does not make live HTTP or DNS requests**.

Expected test interpretation:

- **PASS** (green): a normal behavior works.
- **FAIL** (red): behavior is broken. At present the `httpcore.HTTPError` catch is a known incompatibility with HTTPCore 1.0.9.
- **XFAIL** (yellow): a known security gap the test is intentionally tracking (custom Host header, custom `sni_hostname`, and different path on the approved origin).
- **XPASS** (red, when marked `strict=True`): code now passes an expected-failure test, so remove the xfail marker and keep it as a permanent regression test.

##### HTTPcore exception compatibility fix

The `httpcore.HTTPError` exception name is not defined in HTTPcore 1.0.9. In `crawler/src/crawler/fetcher/transport.py` define:

```python
CORE_ERRORS = (
    httpcore.TimeoutException,
    httpcore.NetworkError,
    httpcore.ProtocolError,
    httpcore.ProxyError,
    httpcore.UnsupportedProtocol,
)
```

Replace the three occurrences of `except httpcore.HTTPError as exc:` with `except CORE_ERRORS as exc:`. Run the tests again. Keep the explicit subtype-to-HTTPX exception mapping as-is.

Also verify `PolicyCoordinator` imports shared `FetcherSecurityError` / `ResponseTooLargeError` from `crawler.fetcher.errors` rather than redefining them.

## frontier

### Running the frontier tests

What each test checks is in the cases below.

#### Pytest (no database)

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests/crawler/frontier -q
```

This runs `test_urls.py` and `test_scope.py`. Both use fake sessions, so no database is needed.

#### Database script

`test_enqueue_target.py` is a script, not a pytest test (it has no `test_` function). It needs a PostgreSQL database reachable through the backend's `DATABASE_URL`, with at least one enabled source (run the source seeder first). It rolls its insert back.

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/frontier/test_enqueue_target.py
```

It prints `TEST PASSED` on success.

### Frontier test cases

Tests for URL normalization, crawl scope, and enqueueing crawl targets into the frontier.

#### test_urls.py

Pure unit tests for `crawler.frontier.urls.normalize_url`. No database needed.

| Test | What it checks |
| --- | --- |
| `test_normalize_url` (parametrized) | Scheme and host are lowercased, default ports (`:443` for https, `:80` for http) are dropped, non-default ports (`:8443`) are kept, fragments are removed, an empty path becomes `/`, query strings are kept as-is, and IPv6 hosts keep their brackets. |
| `test_invalid_url` (parametrized) | `ValueError` is raised for an empty string, `javascript:` and `ftp:` schemes, a URL with no host, embedded credentials (`user:password@`), a non-numeric port, out-of-range ports (`99999`, `0`), and invalid percent-encoding (`%ZZ`). |
| `test_idempotency` | Normalizing an already normalized URL returns the same string. |

#### test_scope.py

Unit tests for `CrawlScope` and the budget logic in `enqueue_targets`, using fake sessions instead of a real database.

| Test | What it checks |
| --- | --- |
| `test_depth_boundary_and_child_depth` | `_create_discovered_targets` produces no children when the parent is already at `max_depth` (3), and gives children `parent_depth + 1` when the parent is below it. |
| `test_explicit_path_scope` (parametrized) | With `allowed_path_prefixes: ['/docs/']`, `/docs` and `/docs/python` are allowed, while `/docstrings`, `/archive`, and path traversal attempts (`/docs/../archive`, `/docs/%2e%2e/archive`) are rejected. |
| `test_invalid_limits_rejected` (parametrized) | `CrawlScope.from_config` raises `ValueError` for a negative, boolean, or too large (`101`) `max_depth`, a `max_pages` of `0` or a string, and an empty or non-list `allowed_path_prefixes`. |
| `test_duplicate_urls_do_not_use_remaining_budget_and_lock_precedes_count` | With 9 of 10 pages used, `enqueue_targets` takes a `pg_advisory_xact_lock` before counting existing targets, skips URLs that already exist and in-batch duplicates, and inserts only one new URL (`/b`) to fill the remaining budget. |
| `test_full_source_does_not_insert_more_urls` | When the source already has `max_pages` targets, `enqueue_targets` inserts nothing and returns `0`. |

#### test_enqueue_target.py

A script-style integration check (run with `python`, not collected as a pytest test since it has no `test_` function). It needs a live PostgreSQL database with at least one enabled `Source`.

- Builds a `CrawlTargetCreate` for a unique `https://example.com/test/<uuid>` URL.
- Calls `enqueue_target` twice with the same target and asserts the first call returns `True` (inserted) and the second returns `False` (duplicate ignored).
- Rolls back the transaction so no test data is left behind. Uses a selector event loop on Windows.

## parser

### Running the parser tests

What each test checks is in the cases below.

These tests are fully offline: no network, database, policy coordinator, or worker.

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests/crawler/parser -q
```

`test_html_parser.py` is a `unittest` suite, so it can also be run on its own:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/parser/test_html_parser.py
```

The RSS/Atom, JSON API, and sitemap parsers are tested in [crawler/tests](README.md).

### Parser test cases

Offline tests for the HTML parser. No network, policy coordinator, PostgreSQL, or worker is required.

#### test_html_parser.py

Uses a shared `HTML_FIXTURE` page (Open Graph title, description, author, published time, robots and keywords meta, a relative canonical link, a `<nav>`, a `<main>` with headings, a code block, three links, and a `<footer>`).

##### TestParserIntegration (`parse`)

| Test | What it checks |
| --- | --- |
| `test_complete_html_pipeline` | Parsing the fixture returns one `ParsedDocument` with the Open Graph title, description, author, an absolute canonical hint without the fragment, a UTC `published_at`, headings, body text, an indented code block, language, robots directives, and keywords. Nav and footer text are excluded. Links are resolved, fragments stripped, duplicates collapsed (2 links), anchor text kept, and `nofollow` detected. |
| `test_xhtml_supported` | `application/xhtml+xml` is accepted and parsed. |
| `test_header_charset_decodes_text` | A `charset=iso-8859-1` in the Content-Type header is used to decode the body (`café`). |
| `test_title_falls_back_to_h1` | With no `<title>` or `og:title`, the first `<h1>` becomes the title. |
| `test_unsupported_or_missing_content_type` | `None`, empty, JSON, RSS, and PNG content types raise `UnsupportedContentTypeError`. |
| `test_invalid_charset` | An unknown charset raises `ContentDecodeError`. |
| `test_empty_html_body` | Empty or whitespace-only bodies raise `MalformedContentError`. |
| `test_body_requires_bytes` | Passing a `str` instead of `bytes` raises `TypeError`. |
| `test_invalid_page_urls` | Relative, `ftp:`, credentialed, bad-port, zero-port, and space-containing page URLs raise `ParserError`. |
| `test_empty_document_still_has_result` | An empty `<body>` still yields one document with an empty body and no links. |

##### TestMainContentExtractor (`extract_main_content`)

| Test | What it checks |
| --- | --- |
| `test_main_content_over_navigation_and_footer` | `<main>` content is used, nav and footer are excluded, and the original soup is not mutated. |
| `test_preserves_code_indentation` | Indentation inside `<pre><code>` is preserved in `code_blocks` and the body. |
| `test_falls_back_to_article` | Without `<main>`, `<article>` is used and the nav is excluded. |
| `test_falls_back_to_body` | Without `<main>` or `<article>`, `<body>` text is used. |
| `test_excludes_hidden_and_noise` | Elements with `hidden`, `aria-hidden="true"`, a `cookie-banner` class, or `display:none` are dropped. |
| `test_invalid_input` | A non-BeautifulSoup argument raises `TypeError`. |

##### TestMetadataExtraction (`extract_metadata`)

| Test | What it checks |
| --- | --- |
| `test_extracts_metadata_without_mutating_soup` | Title, description, author, UTC `published_at`, and robots directives are extracted, and the soup is unchanged. |
| `test_canonical_is_only_a_hint` | A cross-host canonical URL is kept (fragment removed) as a hint rather than rejected. |
| `test_invalid_canonical_falls_back_to_og_url` | A `javascript:` canonical is ignored and the relative `og:url` is resolved and used instead. |
| `test_missing_optional_metadata` | Missing title, description, canonical, and published date come back as `None`. |
| `test_invalid_page_url` | A relative page URL raises `ValueError`. |

##### TestLinkExtraction (`extract_links`)

| Test | What it checks |
| --- | --- |
| `test_relative_links_fragments_and_duplicates` | Relative links are resolved against the page URL, fragments stripped, duplicates collapsed, and fragment-only links skipped. The first anchor text wins. |
| `test_base_href` | A `<base href>` is used to resolve relative links. |
| `test_rejects_non_http_and_malformed_destinations` | `mailto:`, `javascript:`, `data:`, credentialed, and bad-port links are dropped; only the valid link remains. |
| `test_cross_host_link_is_discovered_but_not_authorized` | External-host links are returned; authorizing them is left to the frontier/coordinator. |
| `test_nofollow_and_rel` | The `rel` tokens are exposed and `nofollow` is set. |
| `test_max_links` | `max_links=1` returns only the first link. |
| `test_invalid_inputs` | A non-soup argument raises `TypeError`; `max_links=0` and a relative page URL raise `ValueError`. |

#### test_robots_metadata.py

| Test | What it checks |
| --- | --- |
| `test_all_applicable_meta_tags_are_respected` (parametrized) | Every applicable robots meta tag is combined: a `noindex` wins regardless of tag order, tags for `DevelopersEyeBot` (case-insensitive) apply, tags for `OtherBot` are ignored, and a `noindex` at the end of a very long content value is still found. It also checks that `process()` marks the document as skipped exactly when `noindex` applies. |

## policy_and_politeness

### Running the policy and politeness tests

What each test checks is in the cases below.

This folder mixes pytest suites and standalone Colorama scripts. Run each kind the right way.

#### Pytest suites (offline)

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests/crawler/policy_and_politeness/test_robots_rules.py crawler/tests/crawler/policy_and_politeness/test_redirect_policy.py crawler/tests/crawler/policy_and_politeness/test_politeness_policy.py crawler/tests/crawler/policy_and_politeness/test_policy_coordinator.py -q
```

These mock DNS, robots, and the fetcher, so there is no network or database access.

#### Standalone scripts

Each script has its own runner and prints PASS/FAIL lines with a summary.

Offline, no database:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/policy_and_politeness/test_host_policy.py
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/policy_and_politeness/test_dns_policy.py
```

Do not run `test_dns_policy.py` through pytest. It has helper functions named `test_*` that take arguments, so pytest would collect them wrongly. The [crawler/tests README](README.md) excludes it from the pytest run for the same reason.

Needs PostgreSQL:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/policy_and_politeness/test_robots_policy.py
```

`test_robots_policy.py` uses the backend's `DATABASE_URL` to test the `robots_cache` table. It rolls back its transaction and uses fake hosts with a fake fetcher, but point it at a development or test database, never production.

### Policy and politeness test cases

Tests for host allowlisting, DNS/IP safety, robots.txt rules and caching, redirects, per-host politeness, and the `PolicyCoordinator` that ties them together.

Some files are pytest/unittest suites; others (`test_host_policy.py`, `test_dns_policy.py`, `test_robots_policy.py`) are Colorama scripts with their own `main()` runner and are meant to be run directly with `python -m ...`.

#### test_host_policy.py

Script runner (`main()`) over a table of cases for `host_policy`. No network.

| Group | What it checks |
| --- | --- |
| Suspicious-character detection (`has_suspicious_characters`) | A normal URL is clean. Backslash, raw space, tab, newline, NUL, zero-width space, and bidi override are flagged. A percent-encoded space (`%20`) is not flagged. |
| Hostname normalization (`normalize_hostname`) | Lowercases, strips one trailing root dot, converts IDN to punycode (`bücher.de` to `xn--bcher-kva.de`), keeps IPv4, compresses IPv6. Returns `None` for empty, `.`, leading/trailing hyphen, underscore, empty label, label over 63 chars, hostname over 253 chars, and embedded whitespace. |
| Allowed-host URL validation (`is_allowed_host`) | Accepts http/https on the allowlisted host regardless of case, trailing dot, default ports, IDNA, and IPv6 allowlist entries; allowlist entries are normalized too. Rejects `ftp:`/`file:`/missing scheme, empty or non-string input, missing host, unrelated hosts, deceptive suffixes (`docs.python.org.evil.example`), unlisted subdomains, any userinfo (including `docs.python.org@evil.example`), non-default/wrong/alphabetic/out-of-range/empty ports, malformed IPv6 brackets, backslash, newline, zero-width characters, and an empty allowlist. Invalid allowlist entries are ignored rather than failing. |

#### test_dns_policy.py

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

#### test_robots_rules.py

Pytest unit tests for robots.txt matching in `robots_policy`.

| Test | What it checks |
| --- | --- |
| `test_path_matching` (parametrized, 21 cases) | `*` wildcards and `$` end anchors (query strings defeat `$`), longest match wins between Allow/Disallow, Allow wins on equal length, empty `Disallow:` allows all, paths are case-sensitive, percent-encoding is compared after decoding unreserved characters and UTF-8, but `%2F` is not treated as `/`, encoded `%2A`/`%24` are literal `*`/`$`, wildcards in query patterns, multi-wildcard patterns, `/robots.txt` is always allowed, and inline `#` comments are stripped. |
| `test_merge_repeated_matching_groups` | Two separate groups for the same user agent are merged. |
| `test_specific_group_replaces_wildcard_case_insensitively` | A group naming `developerseyebot` (any case) replaces the `*` group for `DevelopersEyeBot/1.0`. |
| `test_multiple_agents_and_other_records_do_not_end_group` | A BOM, multiple `User-agent` lines, and a `Sitemap` line do not break the group; `/private` is still disallowed. |
| `test_empty_specific_group_allows_without_wildcard_fallback` | An empty bot-specific group allows everything and does not fall back to the `*` group's `Disallow: /`. |
| `test_nontext_rejected` | `parse_robots(None)` raises `TypeError`. |

#### test_robots_policy.py

Script runner (`main()`) that uses a real PostgreSQL session (rolled back at the end) and a `FakeFetcher` so no robots.txt is fetched over the network. Do not run against production.

| Section | What it checks |
| --- | --- |
| Origin and robots URL | `get_robots_origin` strips path, query, fragment, and default port. `get_robots_url` points to `/robots.txt` at the site root, keeps the scheme and non-default ports, and rejects `file:` URLs. |
| Parsing and permissions | Bot-specific Allow/Disallow rules apply, `*` rules apply to other bots, an empty file allows everything, and non-text input raises `TypeError`. |
| `robots_cache` operations | A missing origin returns `None`. Saving stores status and raw text with timezone-aware timestamps and a positive TTL. Saving again upserts (no duplicate rows). An expired row is treated as a miss. |
| Coordinator ALLOW/DENY and cache reuse | A 200 with a permitted path gives `ALLOW` and fetches only the origin's `robots.txt`. A second evaluation uses the fresh cache (no fetch) and returns `DENY` for a disallowed path. |
| HTTP status and failures | 404 means `ALLOW` and is cached (no refetch). 403 gives `DENY`. 503 gives `DEFER` with the default delay and is not cached. 429 gives `DEFER` with the supplied retry delay. A fetch error, an unhandled 302, an oversized body (not cached), and a non-text body all give `DEFER`. |
| Validation | `javascript:` URLs, an empty user agent, a non-positive cache TTL in `save_robots_cache`, and a `cache_ttl_seconds=0` in `evaluate_robots_policy` all raise `ValueError`. |

#### test_redirect_policy.py

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

#### test_politeness_policy.py

Unittest suite for `politeness_policy`.

| Class | What it checks |
| --- | --- |
| `TestHostKey` | `get_host_key` returns the hostname, gives the same key across paths, schemes, and ports, raises `ValueError` for non-URLs, relative paths, and `ftp:`, and `TypeError` for `None`. |
| `TestRetryAfter` | `parse_retry_after` handles seconds, surrounding whitespace, `0`, a missing header (`None`), an invalid value (`None`), a future HTTP date (about 120 s), a past date (`0`), and caps a huge number at `MAX_BACKOFF_SECONDS`. |
| `TestConfiguration` | Defaults are 2 concurrent per host, 2.0 s interval, 60 s backoff. Custom values are kept. Zero, negative, bool, or float concurrency, negative or NaN interval, infinite backoff, and non-positive max backoff raise `ValueError`. |
| `TestPolitenessManager` (async) | Host state is created on acquire, reused for the same host, and separate per host. Two slots per host are granted, a third waits until one is released, peak concurrency never exceeds the limit across 10 workers, and different hosts do not block each other. The minimum interval is enforced and `0` means no wait. `apply_backoff` delays the next acquire, never shortens an existing backoff, is capped at the max, and rejects negative, NaN, infinite, or bool values. `record_response` sets a backoff for 429 and 503, does nothing for 200, and falls back to the default backoff for an invalid `Retry-After`. Releasing an unknown host or releasing twice raises `ValueError`. `polite_slot` releases on exceptions, and cancelling a waiting acquire releases its slot. |

#### test_policy_coordinator.py

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

## processing

### Running the processing tests

What each test checks is in the cases below.

These tests are fully offline: no HTTP, DNS, database, or worker.

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests/crawler/processing -q
```

For colored PASS/FAIL output grouped by stage (normalize, classify, fingerprint, processor), run the suite directly:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/processing/test_processing.py
```

`test_fingerprint.py` has no assertions. It only prints three values when imported (`True`, `False`, `64`), so check those by eye:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/processing/test_fingerprint.py
```

### Processing test cases

Offline tests for content processing: `ParsedDocument -> normalize -> classify -> fingerprint -> ProcessingResult`. No HTTP, DNS, PostgreSQL, or worker is needed.

#### test_processing.py

A unittest suite with a Colorama runner when run directly (`python crawler/tests/crawler/processing/test_processing.py`). Fixtures `parsed_doc()`, `normalized_doc()`, and `parse_result()` build documents with only the fields under test overridden.

##### Test01Normalization (`normalize_document`)

| Test | What it checks |
| --- | --- |
| `test_cleans_short_fields` | Extra spaces and tabs are collapsed in title, description, and author. |
| `test_cleans_body_and_blank_lines` | Body whitespace is collapsed, `\r\n` becomes `\n`, and runs of blank lines shrink to one. |
| `test_preserves_code_indentation` | Code blocks keep their indentation in both the body and `code_blocks`. |
| `test_cleans_headings_and_code_blocks` | Headings are whitespace-collapsed, empty headings and empty code blocks are dropped, and code is trimmed of surrounding blank lines but keeps leading indentation. |
| `test_normalizes_unicode_nfc` | Decomposed Unicode (`e` + combining accent) is normalized to NFC (`é`). |
| `test_removes_fragment_from_url` | The `#fragment` is removed from the document URL. |
| `test_accepts_same_host_canonical_hint` | A relative same-host canonical hint is resolved and used (fragment removed). |
| `test_rejects_external_canonical_hint` | A canonical hint on another host is ignored; the page URL is kept. |
| `test_rejects_https_downgrade_hint` | An `http://` canonical hint for an `https://` page is ignored. |
| `test_rejects_bad_canonical_hint_without_failing` | A `javascript:` canonical hint is ignored without raising. |
| `test_does_not_mutate_source_metadata` | Changing the normalized metadata (including nested dicts) does not affect the source document. |
| `test_rejects_invalid_source_urls` | `ftp:`, credentialed, space-containing, and relative URLs raise `ValueError`. |
| `test_rejects_wrong_input_type` | A non-`ParsedDocument` input raises `TypeError`. |
| `test_rejects_bad_code_block_types` | A non-string code block raises `TypeError`. |

##### Test02Classification (`classify_document`)

Each URL check also asserts the method starts with `rules:` and confidence is between 0 and 1.

| Test | What it checks |
| --- | --- |
| `test_github_issue` | GitHub `/issues/N` is `ISSUE` with method `rules:github_issue`. |
| `test_github_repository` | A GitHub `owner/repo` URL is `REPOSITORY`. |
| `test_github_discussion` | GitHub `/discussions/N` is `DISCUSSION`. |
| `test_gitlab_issue` | GitLab `/-/issues/N` is `ISSUE`. |
| `test_stackoverflow_question_not_help_page` | Stack Overflow `/questions/...` is `QUESTION`, but `/help` is `OTHER`. |
| `test_reddit_discussion` | A Reddit `/comments/` URL is `DISCUSSION`. |
| `test_docs_host` | A `docs.` host is `DOCUMENTATION`. |
| `test_tutorial_path_overrides_documentation_host` | A `/tutorial/` path on a docs host is `TUTORIAL`. |
| `test_blog_platform` | A dev.to URL is `BLOG`. |
| `test_event_platform` | A Meetup `/events/` URL is `EVENT`. |
| `test_title_fallback` | With no URL rule, a "Getting Started with Docker" title gives `TUTORIAL` and a `docker` tag. |
| `test_article_metadata_fallback` | `og:type: article` metadata gives `BLOG`. |
| `test_unknown_page_falls_back_to_other` | An unmatched page is `OTHER` with confidence `0.0`. |
| `test_does_not_match_fake_github_domain` | `notgithub.com` is not treated as GitHub. |
| `test_tags_from_short_fields_not_body` | Tags come from title and description in order (`python`, `fastapi`, `postgresql`, `docker`), not from body text. |
| `test_rejects_bad_document_type` | A non-document input raises `TypeError`. |
| `test_rejects_non_http_canonical_url` | An `ftp:` canonical URL raises `ValueError`. |

##### Test03Fingerprint (`fingerprint_document`)

| Test | What it checks |
| --- | --- |
| `test_sha256_is_lowercase_hex` | The hash is 64 lowercase hex characters. |
| `test_same_document_same_hash` | Hashing is deterministic. |
| `test_url_author_and_metadata_do_not_change_hash` | URL, canonical URL, author, metadata, and published date are not part of the hash. |
| `test_body_change_changes_hash` | Changing the body changes the hash. |
| `test_title_and_description_change_hash` | Changing title or description changes the hash. |
| `test_headings_and_code_blocks_change_hash` | Changing headings or code blocks changes the hash. |
| `test_different_field_boundaries_do_not_collide` | `title="ab", description="c"` and `title="a", description="bc"` hash differently. |
| `test_rejects_wrong_input` | A non-document input raises `TypeError`. |
| `test_rejects_invalid_code_blocks` | A non-string code block raises `TypeError`. |

##### Test04Processor (`process` and `process_document`)

| Test | What it checks |
| --- | --- |
| `test_one_document_end_to_end` | One document is normalized, classified as `TUTORIAL`, tagged `python`, and given a SHA-256 content hash, with nothing skipped. |
| `test_missing_title_uses_heading` | With no title, the first heading becomes the title and `generated_title` is set. |
| `test_missing_title_uses_url` | With no title or headings, the last URL path segment (`tutorial`) becomes the title and `generated_title` is set. |
| `test_noindex_string_skips_document` | A string `"NOINDEX, FOLLOW"` directive skips the document with reason `NOINDEX`. |
| `test_none_directive_skips_document` | A `none` directive (case and whitespace insensitive) skips with `NOINDEX`. |
| `test_nofollow_alone_does_not_prevent_indexing` | `nofollow` alone still produces a processed document. |
| `test_empty_body_is_skipped` | An empty body with no code skips with `EMPTY_CONTENT`. |
| `test_whitespace_only_body_is_skipped` | A whitespace-only body skips with `EMPTY_CONTENT`. |
| `test_code_only_page_is_accepted` | An empty body with code blocks is processed. |
| `test_invalid_url_becomes_skipped_document` | A `file://` URL skips with `INVALID_URL` instead of raising. |
| `test_malformed_body_becomes_processing_error` | A non-string body skips with `PROCESSING_ERROR`. |
| `test_processes_multiple_documents_independently` | In a batch of four, a noindex and an empty document are skipped while two are processed, and the GitHub issue is classified as `ISSUE`. |
| `test_empty_parse_result_is_valid` | An empty parse result gives empty documents and skipped tuples. |
| `test_source_url_is_preserved` | The result keeps the parse result's `source_url`. |
| `test_classification_metadata_is_preserved` | Original metadata is kept, classification `method` and `confidence` are added, and the source metadata is not mutated. |
| `test_noindex_short_circuits_classification` | A noindex document is skipped before `classify_document` is called (patched to fail if called). |
| `test_different_urls_same_content_not_deduped_here` | Two URLs with identical content are both processed and share the same content hash; dedup happens later. |
| `test_wrong_processor_inputs_raise_type_error` | Wrong input types to `process_document` and `process` raise `TypeError`. |

#### test_fingerprint.py

A script-style check with no `test_` functions or asserts; it prints results at import time. It builds three `NormalizedDocument`s and prints whether the hash is the same for the same content on a different URL (expected `True`), different for changed body content on the same URL (expected `False`), and 64 characters long.

## scheduler

### Running the scheduler tests

What each test checks is in the cases below. `test1_report.md` and `image.png` are an earlier run report.

The four scripts below are standalone, not pytest tests. Each one needs PostgreSQL through the backend's `DATABASE_URL`, with migrations applied. They create a uniquely named temporary source and targets inside one transaction and roll it back, so nothing is left behind. Still, point them at a development or test database, never production.

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/scheduler/test_repository.py
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/scheduler/test_complete_target.py
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/scheduler/test_fail_target.py
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/scheduler/test_round_robin.py
```

Each prints PASS lines and a final success message, then `Test transaction rolled back`. A failed check prints FAIL and raises.

On Windows the scripts switch to a selector event loop themselves, which asyncpg needs.

`test_round_robin` disables every other source inside its transaction so only its own sources take turns. The rollback restores them, but while it runs it holds row locks on the whole `source` table, so do not run it while a crawler worker is using the same database.

##### Concurrent claim tests (pytest)

`test_concurrent_claims.py` needs committed rows, so it is a pytest file like the worker tests. It runs only when `TEST_DATABASE_URL` points at a migrated, dedicated database with `test` in its name. From `crawler/`:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/developers_eye_test"
poetry run pytest tests/crawler/scheduler/test_concurrent_claims.py -v
```

##### Claim benchmark

`bench_claim.py` measures `claim_targets()` latency and how fast 1, 4 and 8 workers drain the frontier. It takes the `repository.py` to measure, so you can compare an old copy with the current one. Results and the exact commands are in [EXP-0001](../../0_tech_docs/crawler/scheduler-and-leases/EXP-0001-claim-path-concurrency-benchmark.md). It needs `BENCH_DATABASE_URL`, also a database with `test` in its name.

```powershell
$env:BENCH_DATABASE_URL = $env:TEST_DATABASE_URL
poetry run python tests/crawler/scheduler/bench_claim.py src/crawler/scheduler/repository.py current
```

### Scheduler test cases

Integration tests for `crawler.scheduler.repository`. Four files are script-style (`python <file>`, with a `main()` and a selector event loop on Windows). Each one opens a real PostgreSQL transaction, creates a uniquely named temporary `Source` and `CrawlTarget` rows, and rolls everything back at the end. `test1_report.md` and `image.png` in this folder are an earlier run report. `test_concurrent_claims.py` is a pytest file instead, because it needs committed rows and two connections; `bench_claim.py` is a benchmark, not a test.

#### test_repository.py

Claiming targets and recovering expired leases (`claim_targets`, `recover_expired_leases`). Setup: two queued, due targets with priority 10 and 5.

| Check | What it verifies |
| --- | --- |
| Claim highest priority | `claim_targets(limit=1, source_id=...)` returns the priority 10 target first. |
| Claim second | The next claim returns the priority 5 target. |
| Nothing left | A further claim for the source returns `[]`, since both are now leased. |
| Active leases untouched | `recover_expired_leases` returns `0` while leases are still valid. |
| Expired lease recovered | After moving one target's `lease_until` into the past, recovery returns `1`, that target goes back to `queued` with `lease_until` cleared, `failure_count` 1 and a retry in the future, and the other target stays `leased`. The test flushes before `refresh()`, because recovery changes ORM objects without flushing. |
| Reclaim recovered target | After making the recovered target due again, it can be claimed again (pinned with `source_id`, since round robin picks across all sources) and is `leased`. |
| Invalid parameters | `limit=0` and `lease_seconds=0` raise `ValueError`. |

#### test_round_robin.py

Round-robin BFS claiming (`claim_targets`), 21 checks. How the claim works is in [REPOSITORY_README.md](../src/crawler/scheduler/docs/REPOSITORY_README.md#how-claim_targets-picks-work-round-robin-bfs). `claim_targets()` looks across every source, so the test first disables all other sources inside its transaction; the rollback turns them back on. Each section creates its own sources so earlier ones cannot interleave.

| Section | What it verifies |
| --- | --- |
| 1. Rotation in one call | Sources A (3 due targets), B (2) and C (1), never claimed. `claim_targets(limit=6)` returns six targets from sources A, B, C, A, B, A. |
| 2. BFS inside a source | Source A's targets come out as priority 80 (depth 3), then priority 50 depth 0, then priority 50 depth 2. Source B gives depth 0 before depth 1. Every claimed target is `leased`. |
| 3. `last_claimed_at` | Set on A, B and C, and ordered C < B < A to match each source's last turn. A further claim returns `[]`. |
| 4. Least recently claimed first | D was last claimed 1 h ago and E 2 h ago, two targets each. Three `limit=1` calls pick E, D, E. |
| 5. Skipped sources | A disabled source with a due target and an enabled source whose only target is not due yet. `claim_targets(limit=5)` returns only D's remaining target; both skipped targets stay `queued` and both sources keep `last_claimed_at` empty. |
| 6. `source_id` filter | With another source holding due work, `source_id=H, limit=2` returns two targets, both from H, and `limit=10` then returns H's last one. |
| 7. Lease and validation | `lease_seconds=120` gives a `lease_until` about 120 s after the claim. `limit=0`, `lease_seconds=0` and `source_id=0` raise `ValueError`. |

Not covered here: a source skipped because another worker holds its row or all its due targets locked (`SKIP LOCKED`, the `unavailable` set). That needs two connections on committed rows, which these roll-back-only scripts avoid.

#### test_complete_target.py

Successful completion (`complete_target`), 12 checks. Setup: three leased targets with `failure_count=3`, two with an active lease and one with an expired lease.

| Check | What it verifies |
| --- | --- |
| 1. Success | Completing with the matching active lease returns `True`. |
| 2. State | `leased` becomes `queued`. |
| 3. Lease cleared | `lease_until` is `NULL`. |
| 4. Fetch time | `last_fetched_at` is set. |
| 5. Next crawl | `next_fetch_at` is `last_fetched_at + 86400` seconds (within 2 s). |
| 6. Failures reset | `failure_count` goes back to `0`. |
| 7. Duplicate | Completing the same target again returns `False`. |
| 8. Mismatched lease | A wrong `expected_lease_until` returns `False` and leaves the target `leased`. |
| 9. Expired lease | An already-expired lease returns `False` and leaves the target `leased`. |
| 10 to 12. Validation | Target ID `0`, a crawl interval of `0`, and a timezone-naive lease timestamp raise `ValueError`. |

#### test_fail_target.py

Failure handling and retry backoff (`calculate_retry_delay`, `fail_target`). Uses the database `now()` as the reference time. Setup: six leased targets with failure counts 0, 2, 6, 20, plus one for a stale lease and one with an expired lease.

| Section | What it verifies |
| --- | --- |
| Exponential backoff | `calculate_retry_delay` gives 60, 120, 240, 480, 960, 1920 s for failures 1 to 6, and is capped at 3600 s for 7, 8, and 10. |
| First failure | Returns `True`, sets `state` to `queued`, clears the lease, increments `failure_count` 0 to 1, schedules a retry 60 s out, and leaves `last_fetched_at` unchanged. |
| Third failure | Count goes 2 to 3 and the retry is 240 s out. |
| Delay cap | The seventh failure retries after 3600 s; at 21 failures the counter keeps increasing but the delay stays at 3600 s. |
| Lease ownership | A duplicate failure report returns `False` and does not increment the count. A mismatched or expired lease returns `False` and leaves the target `leased` with count `0`. A nonexistent target ID returns `False`. |
| Parameter validation | `calculate_retry_delay` rejects `failure_count=0`, `base_delay_seconds=0`, and a max delay below the base. `fail_target` rejects target ID `0`, a zero base delay, a max below the base, and a timezone-naive lease, all with `ValueError`. |

#### test_concurrent_claims.py

Concurrent claiming on committed rows (pytest, 4 tests). Needs `TEST_DATABASE_URL` pointing at a dedicated database with `test` in its name. Each test creates its own sources and targets, disables other sources while it runs, and deletes its rows and re-enables the others afterwards. Why claims work this way: [ADR-0001](../../0_tech_docs/crawler/scheduler-and-leases/ADR-0001-round-robin-claims-without-source-locks.md). All four tests fail on the first round-robin version (source row locked during the claim) and pass now.

| Test | What it verifies |
| --- | --- |
| Single source, overlapping claims | One source with 6 targets. A first transaction claims 3 and stays open while a second transaction claims. The second also gets 3, with no target in both, and all 6 end up `leased`. |
| Multi source, overlapping claims | Two sources with 4 targets each. Two overlapping `limit=2` claims each get exactly one target from each source, with no overlap. A third claim also gets one from each source. |
| Parallel drain, 1 x 60 | 4 workers loop claim-and-commit until nothing is due. Every target is claimed exactly once, and no worker gets `[]` while an unlocked due target exists. |
| Parallel drain, 6 x 10 | Same as above with 6 sources, and every source ends up with `last_claimed_at` set. |

A `lock_timeout` of 5 s on the test connections turns a lock wait that never ends into a failure instead of a hang.

## worker

### Running the worker tests

What each test checks is in the cases below.

#### Offline pytest suites

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests/crawler/worker -q -rs --ignore=crawler/tests/crawler/worker/test_live_pipeline.py
```

`test_availability.py`, `test_deadlock_retry.py`, `test_monitoring.py`, and `test_recovery.py` use fake sessions and mocks. `test_postgres_pipeline.py` is skipped unless `TEST_DATABASE_URL` is set, and `-rs` shows that skip.

#### PostgreSQL pipeline tests

`test_postgres_pipeline.py` needs a dedicated, migrated test database. The URL must use `postgresql+asyncpg` and the database name must contain `test`, or the tests fail on purpose. Each test creates its own source and deletes its rows afterwards.

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:55438/developers_eye_ingestion_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
.\crawler\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\crawler\.venv\Scripts\python.exe -m pytest crawler/tests/crawler/worker/test_postgres_pipeline.py -q
```

The [crawler/tests README](README.md) has more on setting up this database.

#### Live pipeline (real internet)

`test_live_pipeline.py` is a script, not a pytest test. It fetches real pages through the policy coordinator, parses and processes them, and prints the results. It needs `DATABASE_URL` for the robots cache, rolls the session back, and stores nothing.

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/worker/test_live_pipeline.py
```

By default it fetches five `docs.python.org` pages. To test other pages, pass each URL and its host explicitly:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/tests/crawler/worker/test_live_pipeline.py --allow-host docs.python.org --url https://docs.python.org/3/tutorial/
```

It exits `0` only if at least one document was accepted with no errors.

### Worker test cases

Tests for the crawl worker: job processing, finalization, telemetry, deadlock retries, lease recovery, and the monitoring API. Most tests use fake sessions and mocks; `test_postgres_pipeline.py` needs a dedicated test database and `test_live_pipeline.py` hits the real internet.

#### test_availability.py

Network-free pytest tests for how missing pages are handled.

| Test | What it checks |
| --- | --- |
| `test_missing_pages_are_retained_as_unavailable_and_removed_from_search` (404, 410) | When `_finalize` handles a 404 or 410, it issues an `UPDATE document` (keeping the row and linking `last_crawl_target_id`), deletes the document's `search_index` row, never runs `DELETE FROM document`, and still completes the target. |
| `test_successful_observation_restores_document_availability` | `upsert_document` returns the document ID and its SQL resets `is_available`, `unavailable_at`, and `unavailable_http_status`, so a page that comes back becomes available again. |

#### test_deadlock_retry.py

Pytest tests for `jobs.retry_deadlocked_finalization`, with `sleep` and jitter mocked.

| Test | What it checks |
| --- | --- |
| `test_deadlock_retries_fresh_operation_without_refetch` | Two deadlocks (SQLSTATE `40P01`) followed by success give 3 calls in total, with backoff sleeps of 0.2 s and 0.4 s, and return the result. |
| `test_deadlock_exhaustion_propagates_last_error` | Constant deadlocks stop after 4 attempts and re-raise the last `DBAPIError`. |
| `test_other_database_errors_and_cancellation_are_not_retried` | A unique violation (`23505`) or `CancelledError` is raised after one attempt with no retry. |

#### test_monitoring.py

Network-free regression tests for pipeline checkpoints, storage events, and the authenticated crawler report API. Uses a fake session that compiles every statement for PostgreSQL to catch SQL mistakes.

| Test | What it checks |
| --- | --- |
| `test_real_parser_pipeline_checkpoints` (8 scenarios) | Runs `process_job` with a mocked fetch for `stored`, `noindex` (via `X-Robots-Tag`), `http404`, `mime` (PDF), `parse_error`, `blocked` (policy `DENY`), `not_modified` (304), and `store_error`. The first checkpoint is always `FETCH running`; `fetch_success` is false only for 404 and blocked; stored pages are parsed and accepted with a `PARSE` checkpoint; noindex is skipped with reason `noindex`; parse errors are tagged `error_category: parse`; the wrong MIME type reports `unsupported MIME`; and a storage failure records `STORE failed` with `stored: 0`, re-raises, and calls `recover_failed_claim`. |
| `test_atomic_storage_events_and_dedup` (5 decisions) | `_finalize` emits a `DEDUP` event with outcome `new`, `unchanged`, `updated`, or `duplicate` (with `matching_document_id`), saves one document, and records the stored document ID in the `STORE` event. With a `stale` (expired) lease, nothing is upserted and the outcome is `stale`. |
| `test_telemetry_failure_does_not_fail_crawl` | `checkpoint` swallows a broken session factory instead of raising. |
| `test_monitoring_routes_enforce_auth_and_validate_filters` | `/admin/crawler/monitor`, `/documents/1`, and `/attempts/1` return 401 without the bearer key and never reach the handler. With the key, `days=0` and an unknown `status` return 422, and a valid request returns 200 with `Cache-Control: private, no-store`, passes `source_id` through, and runs in a `READ ONLY` transaction. |

#### test_recovery.py

Network-free pytest tests for lease and attempt recovery.

| Test | What it checks |
| --- | --- |
| `test_abandoned_attempt_is_terminal_and_preserves_original_failure_category` | `close_abandoned_attempts` marks an open attempt `failed` with `finished_at` set, keeps the original `error_category` (`persistence`), emits a `failed` event, and filters by the exact `lease_until`. |
| `test_recovery_never_requeues_a_newer_workers_claim` | If the target now has a newer lease, `recover_failed_claim` does not call `fail_target` and only closes attempts for the old lease (`include_legacy=False`). |
| `test_owned_failure_uses_scheduler_backoff` | If the worker still owns the lease, `recover_failed_claim` calls `fail_target` with that lease. |
| `test_expired_leases_increment_failures_delay_retries_and_reconcile_orphans` | `recover_expired_leases` increments `failure_count` (1 to 2), schedules the retry 120 s out, requeues and clears the lease, closes attempts for both the expired target and an orphaned queued target, uses `SKIP LOCKED`, and filters orphans by `state !=`. |
| `test_timeout_records_exact_claim_and_is_counted_as_failed` | When a job exceeds `job_timeout_seconds`, `execute_target` counts it as both failed and timed out and records the failure for that exact target. |

#### test_postgres_pipeline.py

PostgreSQL regression tests. They are skipped unless `TEST_DATABASE_URL` is set, and fail if it is not `postgresql+asyncpg` with `test` in the database name. Each test creates its own source (`max_depth: 3`, `max_pages: 7`) and deletes all its rows afterwards. `PolicyCoordinator.fetch` is mocked.

| Test | What it checks |
| --- | --- |
| `test_structured_resources_commit_documents_targets_and_attempts` (sitemap, rss, api) | Processing a sitemap, RSS feed, or JSON API target succeeds and enqueues one link. Sitemaps save no document and enqueue a `page` child at depth 0; RSS and API save one document (with `ingestion_format` `rss` or `json_api`) and enqueue a same-kind child (the next page) at depth 1. The attempt is finished with `resource_kind` telemetry, and `inspect_document` can read the document. |
| `test_concurrent_claims_atomic_writes_and_shared_source_budget` | Two concurrent claims of 2 get disjoint targets. Processing all 4 concurrently succeeds, saves 4 documents, leaves no open attempts, and caps total targets at the source's `max_pages` of 7 even though each page links to 4 more. `build_monitor` reports 4 attempted and 4 persisted, and the document detail is available. |
| `test_removed_page_invalidates_index_and_recovers_when_restored` | After a 200 then a 404, the document is marked unavailable with status 404 and its search index row is removed. A later 200 makes it available again with no status. |
| `test_expiration_and_old_worker_recovery_do_not_touch_new_claims` | Recovering an old worker's claim and expired leases fails the old attempts, leaves the newer active attempt open, gives the expired target a failure and a future retry, and leaves the newer lease untouched. |

#### test_live_pipeline.py

A live, rollback-only script (`python crawler/tests/crawler/worker/test_live_pipeline.py`). It is not a pytest test. It runs `PolicyCoordinator -> HTTPXHopFetcher -> parser -> processor` against real URLs (by default five `docs.python.org` pages, or `--url` / `--allow-host`), with one request per host and a 2 s interval. It prints the policy decision, redirect chain, parsed documents, processing results, and a sample of discovered links (never enqueued), and applies `X-Robots-Tag` headers for this bot or `*`. It needs `DATABASE_URL` for the robots cache, rolls the session back, and writes no documents, targets, or index rows. It exits `0` only if at least one document was accepted and there were no errors.

## indexer

### Running the indexer tests

What each test checks is in the cases below.

#### Fast tests (no database)

From `crawler/`:

```powershell
poetry run pytest tests/indexer -v -rs
```

Everything runs except the PostgreSQL tests, which show as skipped. `-rs` prints the skip reasons so a skip is not mistaken for a pass.

To run one layer, name its file, for example:

```powershell
poetry run pytest tests/indexer/test_service_writer.py -v
```

#### PostgreSQL tests

Three tests need a real PostgreSQL server:

- `test_selector.py` (all tests), which creates a temporary schema inside one transaction and rolls it back.
- `test_vector.py::test_postgresql_executes_weighted_text_and_code_vectors`, which only runs a `SELECT`.
- `test_indexer.py::test_final_indexer_lifecycle_against_postgresql`, which uses TEMP tables on its own connection.

None of them write to your real `document` or `search_index` tables, but still point them at a separate test database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:5432/developers_eye_test"
poetry run pytest tests/indexer -v -rs
```

`TEST_DATABASE_URL` must use the `postgresql+asyncpg://` driver (`test_selector.py` also accepts `postgresql+psycopg://`).

#### Notes

- `conftest.py` holds the shared fixtures (`config`, `make_document`, `make_index_document`, `candidate`) and adds `src/` to `sys.path`, so the tests also run against the source checkout.
- Async tests use `pytest-asyncio` (`@pytest.mark.asyncio`), which is a crawler dependency.

### Indexer test cases

Tests for the search indexer: `selector -> service (builder -> analyzer -> vector) -> writer -> repository`. Run from `crawler/` with `poetry run pytest tests/indexer -v`. Tests that need PostgreSQL are skipped unless `TEST_DATABASE_URL` is set. See `README.md` in this folder for setup.

| File | Layer | Needs PostgreSQL |
| --- | --- | --- |
| `test_builder.py` | builder | No |
| `test_analyzer.py` | analyzer | No |
| `test_vector.py` | vector | One optional test |
| `test_selector.py` | selector | Yes (skipped without it) |
| `test_repository.py` | repository | No (mocked session) |
| `test_service_writer.py` | service and writer | No (mocked repository) |
| `test_pipeline.py` | builder to analyzer contract | No |
| `test_indexer.py` | full lifecycle | One test yes, one no |

#### conftest.py

Shared fixtures, not tests:

- `config`: an `IndexerConfig` with batch size 10, index version 1, a 100,000 character limit, `english` text search, and `simple` code search.
- `make_document`: builds a crawler `Document` (an available Python async tutorial with headings, a code block, and tags in `metadata_`).
- `make_index_document`: builds the matching `IndexDocument`.
- `candidate`: an `IndexCandidate` for document 10 at the fixed source timestamp.

It also adds `src/` to `sys.path` so the tests run against the source checkout.

#### test_builder.py

Turning a crawler `Document` into an `IndexDocument`, and the index hash.

| Test | What it checks |
| --- | --- |
| `test_prepare_normalizes_text_and_metadata` | `prepare_index_document` applies Unicode NFC, converts `\r\n` and `\r` to `\n`, trims text, drops blank headings and code blocks, keeps code indentation, dedupes tags case-insensitively (first spelling wins), copies `updated_at`, and returns a frozen object. |
| `test_prepare_does_not_mutate_crawler_metadata` | The original `metadata_` dict is unchanged. |
| `test_prepare_rejects_invalid_document_id` | IDs `0`, `-1`, `"10"`, and `True` raise `IndexDocumentError`. |
| `test_prepare_rejects_unavailable_document` | An unavailable document raises `StaleIndexSourceError`. |
| `test_prepare_rejects_invalid_metadata` | Non-object metadata, non-list tags, and non-string headings or code blocks raise `IndexDocumentError` with a field-specific message. |
| `test_prepare_enforces_total_character_limit` | A document over `max_document_chars` raises `IndexDocumentTooLargeError`. |
| `test_build_reloads_document_and_prepares` | `build_index_document` reloads the document with one query and returns the prepared result for the candidate. |
| `test_build_rejects_stale_candidate` (missing, unavailable, updated) | A deleted, unavailable, or newer-than-candidate document raises `StaleIndexSourceError`. |
| `test_build_propagates_database_failure` | Database errors are not swallowed. |
| `test_hash_is_stable_and_version_prefixed` | `calculate_index_hash` is deterministic and is the version prefix plus 64 hex characters. |
| `test_hash_changes_for_index_relevant_fields` | Changing title, description, body, headings, code blocks, tags, canonical URL, or content hash changes the hash. |
| `test_hash_changes_when_index_version_changes` | Bumping `index_version` changes the hash. |
| `test_hash_excludes_source_timestamp` | A recrawl that only changes `source_updated_at` keeps the same hash. |

#### test_analyzer.py

Splitting an `IndexDocument` into weighted text and code fields. No database and no TSVECTOR building.

| Test | What it checks |
| --- | --- |
| `test_analyzer_separates_text_and_code` | Text fields are title (A), tags (A), headings (B), description (B), body (C) with the `english` config. Code fields are tags (A), title (A), code_blocks (B), headings (B), canonical_url (D) with the `simple` config. IDs and timestamp are copied. |
| `test_analyzer_preserves_boundaries_and_code_whitespace` | List items are joined with blank lines, and code indentation is kept. |
| `test_analyzer_skips_optional_blank_fields` | Blank description, headings, tags, and code blocks are left out. |
| `test_analyzer_output_is_frozen` | Results and fields are frozen tuples and dataclasses. |
| `test_analyzer_is_deterministic` | The same input gives an equal result. |
| `test_field_rejects_non_strings` / `test_field_rejects_nul` / `test_field_returns_none_for_whitespace_only` | `_field` rejects non-strings and NUL bytes with `IndexDocumentError`, and returns `None` for whitespace-only text. |
| `test_join_items_does_not_change_indentation` / `test_join_items_rejects_invalid_container_or_elements` | `_join_items` keeps indentation and skips empty items, and rejects lists, `None` items, and non-tuples. |
| `test_analyzer_rejects_wrong_argument_types` | Wrong document or config types raise `TypeError`. |

#### test_vector.py

Building bound, typed PostgreSQL `TSVECTOR` expressions. Most tests only compile SQL; one optional test runs against PostgreSQL.

| Test | What it checks |
| --- | --- |
| `test_empty_vector_is_typed_and_parameterized` | The empty vector is a `CAST('' AS TSVECTOR)` with a bound empty string. |
| `test_field_vector_compiles_as_weighted_tsvector` | A field becomes `setweight(to_tsvector(REGCONFIG, text), 'A')` with the text and config as bound parameters. |
| `test_all_supported_weights_are_compiled_as_literals` | Weights A to D are SQL literals, not parameters. |
| `test_field_values_are_bound_and_not_interpolated_into_sql` | A SQL injection payload and a schema-qualified config never appear in the SQL text. |
| `test_blank_field_yields_empty_vector` | Blank text gives the empty vector with no `to_tsvector`. |
| `test_field_vector_rejects_*` | Non-field input (`TypeError`), non-string text, NUL bytes, invalid weights, and invalid config names (spaces, leading digit, injection, double dots, three parts, too long, quoted) raise `ValueError`. Valid names such as `pg_catalog.english` and `_custom_1` are accepted. |
| `test_combining_*` | Zero fields give the empty vector, one field has no `||`, three fields are joined with `||` in order with their weights, a blank field stays as a valid empty expression, and non-tuple or invalid entries raise `TypeError`. |
| `test_search_vectors_from_real_analyzer_output` | `build_search_vectors` produces text and code vectors with one `to_tsvector` per field and the right configs. |
| `test_search_vectors_does_not_mutate_analyzer_output` / `..._result_is_frozen` / `..._are_deterministic` / `..._allow_empty_field_groups` | No mutation, frozen output, identical SQL across runs, and empty groups give empty vectors. |
| `test_search_vectors_reject_*` | Wrong document or config type, invalid IDs (`0`, `-1`, `True`, `"5"`), invalid timestamps, a field whose `search_config` does not match its group, and non-tuple field groups are rejected. |
| `test_postgresql_executes_weighted_text_and_code_vectors` | Optional, needs `TEST_DATABASE_URL` with asyncpg. Real PostgreSQL stems `Running` to `'run':1A` in the text vector and keeps `'running':1B` in the code vector. |

#### test_selector.py

Picking documents that need indexing or removal, against real PostgreSQL. Needs `TEST_DATABASE_URL` (asyncpg or psycopg). Each test creates a temporary schema with `document` and `search_index` tables (no foreign keys) inside one transaction and rolls it back.

| Test | What it checks |
| --- | --- |
| `test_new_document_needs_indexing` | A document with no index row is not current and is selected with its `updated_at`. |
| `test_current_document_is_skipped` | An index row newer than the document with the current hash prefix is current and not selected. |
| `test_changed_document_is_reselected` | An index row older than the document's `updated_at` is selected again. |
| `test_old_index_version_is_reselected` | An index row with an old version prefix (`v0:`) is selected again. |
| `test_unavailable_document_is_not_indexed_and_is_removed` | An unavailable document is not a candidate for indexing but is a removal candidate. |
| `test_missing_source_document_triggers_cleanup` | An index row with no matching document is a removal candidate. |
| `test_cursor_and_batch_size` | `after_document_id=10` returns only later candidates (20, 30). |

#### test_repository.py

Contract tests for the persistence adapter with a mocked `AsyncSession` (no live database). SQL is compiled for PostgreSQL and inspected.

| Test | What it checks |
| --- | --- |
| `test_get_search_index_loads_only_freshness_metadata` | `get_search_index` returns `StoredIndexState` and selects only `indexed_hash` and `indexed_at`, not the vectors. |
| `test_get_search_index_returns_none_if_missing` | A missing row returns `None`. |
| `test_get_document_for_update_locks_document` | `get_document_for_update` returns `LockedDocumentState`, uses `FOR UPDATE OF document`, and does not commit. |
| `test_get_document_for_update_returns_none_if_missing` | A missing document returns `None`. |
| `test_upsert_uses_bound_parameters_and_updates_both_vectors` | `upsert_search_index` uses `ON CONFLICT (document_id) DO UPDATE` to set both vectors, the hash, and `indexed_at = now()`, binds the hash and text as parameters, returns the ID, and does not commit. |
| `test_upsert_rejects_invalid_hash` | An empty hash, a `v0:` version, non-hex, or uppercase hex raises `ValueError` before any SQL runs. |
| `test_repository_rejects_invalid_document_ids` | `0`, `-1`, `True`, and `"10"` raise `ValueError` in get, lock, and delete, with no SQL run. |
| `test_delete_is_idempotent_and_does_not_commit` | `delete_search_index` uses `DELETE ... RETURNING`, returns `True` when a row was removed and `False` when none existed, and does not commit. |

#### test_service_writer.py

Unit tests for `writer.py` and `service.py` orchestration. The repository functions and pipeline steps are monkeypatched and a fake session factory is used, so no database is needed.

| Test | What it checks |
| --- | --- |
| `test_writer_new_index` | `persist_search_vectors` locks the document, finds no index row, upserts once, and returns `INDEXED`. |
| `test_writer_unchanged_index` | When the stored hash matches and `indexed_at` is newer than the source, nothing is written and the result is `UNCHANGED`. |
| `test_writer_rejects_stale` (4 cases) | A missing document, an unavailable document, a different `source_id`, or a source updated after the vectors were built returns `STALE` without upserting. |
| `test_writer_rebuilds_outdated_timestamp` | Same hash but an `indexed_at` older than the source's `updated_at` is rewritten and returns `INDEXED`. |
| `test_removal_guards_active_sources` (4 cases) | `remove_search_index` returns `REMOVED` when the document is gone or unavailable and a row was deleted, `SKIPPED` when there was no row to delete, and `STALE` (without deleting) when the document is available again. |
| `test_service_full_index` | `index_candidate` runs build, hash, analyze, and vectors, calls the writer once, and returns `INDEXED` with the hash and a non-negative `duration_ms`. |
| `test_service_marks_stale` | A `StaleIndexSourceError` from the builder becomes a `STALE` result and nothing is persisted. |
| `test_service_does_not_swallow_database_errors` | Unexpected errors such as a database outage are re-raised for the worker to handle. |
| `test_service_remove_result` | `remove_candidate` returns the document ID with the writer's `REMOVED` status. |

#### test_indexer.py

End-to-end smoke tests for `selector -> service -> writer -> repository`. (The docstring's run command still mentions the old name `test_final_indexer.py`; the file is `test_indexer.py`.)

| Test | What it checks |
| --- | --- |
| `test_final_local_document_to_sql_expression` | No database. A real `Document` row goes through `prepare_index_document` (duplicate tags collapsed), `calculate_index_hash` (`v2:` prefix), `analyze_index_document` (title at weight A, a `code_blocks` code field), and `build_search_vectors`. The compiled SQL uses `setweight` and `to_tsvector`, and document text is bound rather than put into the SQL. |
| `test_final_indexer_lifecycle_against_postgresql` | Needs `TEST_DATABASE_URL` (asyncpg). Uses only TEMP `document` and `search_index` tables on one connection, so real tables are never touched. It walks the full lifecycle listed below. |

The lifecycle steps in `test_final_indexer_lifecycle_against_postgresql`:

1. Insert one document into the temp table.
2. The selector returns it as a candidate.
3. `index_candidate` returns `INDEXED` with a `v2:` hash, and real full-text search matches `python` (english) and `async` (simple code vector). The selector then returns nothing.
4. Indexing the same revision again returns `UNCHANGED` and keeps the hash.
5. Vectors built before the document was edited are rejected as `STALE` by `persist_search_vectors`, and the stored index is unchanged.
6. The old candidate is `STALE`; a fresh candidate reindexes with a new hash, and the new term becomes searchable.
7. Changing `index_version` to 3 reselects the document and rebuilds it with a `v3:` hash.
8. Marking the document unavailable removes it from candidates and adds it to removals; `remove_candidate` returns `REMOVED`, then `SKIPPED` the second time.
9. Making it available again lets it be reindexed, and a late removal returns `STALE` without deleting the index.
10. Hard-deleting the document cascades and removes its index row.

#### test_pipeline.py

| Test | What it checks |
| --- | --- |
| `test_document_flows_from_builder_to_analyzer` | Smoke test of the builder and analyzer contract: a document prepared by the builder keeps its ID and timestamp through the analyzer, gets a version-prefixed hash, and its body and first code block appear unchanged in the analyzed text and code fields. |
