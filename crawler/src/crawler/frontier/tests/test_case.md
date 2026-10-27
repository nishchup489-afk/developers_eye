# Frontier test cases

Tests for URL normalization, crawl scope, and enqueueing crawl targets into the frontier.

## test_urls.py

Pure unit tests for `crawler.frontier.urls.normalize_url`. No database needed.

| Test | What it checks |
| --- | --- |
| `test_normalize_url` (parametrized) | Scheme and host are lowercased, default ports (`:443` for https, `:80` for http) are dropped, non-default ports (`:8443`) are kept, fragments are removed, an empty path becomes `/`, query strings are kept as-is, and IPv6 hosts keep their brackets. |
| `test_invalid_url` (parametrized) | `ValueError` is raised for an empty string, `javascript:` and `ftp:` schemes, a URL with no host, embedded credentials (`user:password@`), a non-numeric port, out-of-range ports (`99999`, `0`), and invalid percent-encoding (`%ZZ`). |
| `test_idempotency` | Normalizing an already normalized URL returns the same string. |

## test_scope.py

Unit tests for `CrawlScope` and the budget logic in `enqueue_targets`, using fake sessions instead of a real database.

| Test | What it checks |
| --- | --- |
| `test_depth_boundary_and_child_depth` | `_create_discovered_targets` produces no children when the parent is already at `max_depth` (3), and gives children `parent_depth + 1` when the parent is below it. |
| `test_explicit_path_scope` (parametrized) | With `allowed_path_prefixes: ['/docs/']`, `/docs` and `/docs/python` are allowed, while `/docstrings`, `/archive`, and path traversal attempts (`/docs/../archive`, `/docs/%2e%2e/archive`) are rejected. |
| `test_invalid_limits_rejected` (parametrized) | `CrawlScope.from_config` raises `ValueError` for a negative, boolean, or too large (`101`) `max_depth`, a `max_pages` of `0` or a string, and an empty or non-list `allowed_path_prefixes`. |
| `test_duplicate_urls_do_not_use_remaining_budget_and_lock_precedes_count` | With 9 of 10 pages used, `enqueue_targets` takes a `pg_advisory_xact_lock` before counting existing targets, skips URLs that already exist and in-batch duplicates, and inserts only one new URL (`/b`) to fill the remaining budget. |
| `test_full_source_does_not_insert_more_urls` | When the source already has `max_pages` targets, `enqueue_targets` inserts nothing and returns `0`. |

## test_enqueue_target.py

A script-style integration check (run with `python`, not collected as a pytest test since it has no `test_` function). It needs a live PostgreSQL database with at least one enabled `Source`.

- Builds a `CrawlTargetCreate` for a unique `https://example.com/test/<uuid>` URL.
- Calls `enqueue_target` twice with the same target and asserts the first call returns `True` (inserted) and the second returns `False` (duplicate ignored).
- Rolls back the transaction so no test data is left behind. Uses a selector event loop on Windows.
