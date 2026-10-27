# Crawler ingestion test cases

Offline tests for structured-resource ingestion: XML sitemaps, RSS/Atom feeds, and JSON APIs, plus how the worker dispatches them. They use literal XML/JSON and test doubles for network and persistence, but the worker tests still run the real parser and processor. See `README.md` in this folder for how to run them and the database suites.

## test_sitemap.py

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

## test_sitemap_discovery.py

Sitemap seeding, robots.txt `Sitemap:` lines, scope, and worker dispatch, without live network or database writes.

| Test | What it checks |
| --- | --- |
| `test_seed_configuration_host_filter_and_default_sitemap` | `build_initial_targets` returns the base page, configured sitemaps on allowed hosts only (the `evil.test` one is dropped), and the default `/sitemap.xml`. `discover_sitemaps: False` leaves only the page. If the base URL is outside `allowed_path_prefixes`, the first target is a sitemap rather than the page. |
| `test_gzip_file_mime_types_are_only_enabled_for_sitemap_jobs` | `application/gzip` and `application/octet-stream` are allowed for sitemap fetches but not for page fetches. |
| `test_robots_declarations_are_absolute_bounded_and_case_insensitive` | `extract_robots_sitemaps` reads `Sitemap:` case-insensitively, strips comments, dedupes, drops relative and `file://` URLs, and caps the list at 100. A robots 200 decision carries the sitemap URLs. |
| `test_nested_maps_and_page_scope_have_separate_depth_meanings` | Page URLs from a sitemap are kept only if on an allowed host and path, and get depth 0 with `discovered_from_id` set. A nested sitemap index becomes a `sitemap` target at depth 0 but is dropped once the sitemap depth reaches `max_depth`. |
| `test_worker_sitemap_uses_policy_then_normal_finalization` | `process_job` for a sitemap target fetches through the policy coordinator once, stores no documents, and finalizes successfully with the in-scope page enqueued at depth 0. |

## test_feeds.py

`parse_feed` unit tests for RSS and Atom.

| Test | What it checks |
| --- | --- |
| `test_rss_content_extensions_dates_and_invalid_records` | `content:encoded` is used as the body with `<script>` removed, `description` is kept, `dc:creator` becomes the author, `pubDate` is parsed to UTC, relative links are resolved, and `javascript:` links, non-URL GUIDs, and duplicate links are dropped (one document remains). |
| `test_atom_bases_text_html_xhtml_author_and_pagination` | Nested `xml:base` values resolve entry links, escaped titles are decoded, XHTML content is converted to text without scripts, the feed-level author is inherited, an entry with only a `urn:` ID is dropped, and `rel="next"` becomes an `rss` pagination link. |
| `test_bad_feeds_fail` | An empty `<rss/>`, an HTML root, truncated XML, any DOCTYPE, and empty input raise `MalformedContentError`. |
| `test_feed_limits_count_all_items` | `MAX_FEED_ENTRIES` counts every item (even empty ones) and raises `Too many`; `MAX_FEED_BYTES` raises `oversized`. |
| `test_bad_date_does_not_drop_valid_entry_and_guid_must_be_a_url` | An unparseable date leaves `published_at` as `None` but keeps the entry; a URL GUID is used as the link while an opaque GUID is dropped; `parse_record_date` returns `None` for an out-of-range year 1 date with an offset. |

## test_json_api.py

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

## test_ingestion_jobs.py

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
