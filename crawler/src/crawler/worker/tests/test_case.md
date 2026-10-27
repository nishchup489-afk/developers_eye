# Worker test cases

Tests for the crawl worker: job processing, finalization, telemetry, deadlock retries, lease recovery, and the monitoring API. Most tests use fake sessions and mocks; `test_postgres_pipeline.py` needs a dedicated test database and `test_live_pipeline.py` hits the real internet.

## test_availability.py

Network-free pytest tests for how missing pages are handled.

| Test | What it checks |
| --- | --- |
| `test_missing_pages_are_retained_as_unavailable_and_removed_from_search` (404, 410) | When `_finalize` handles a 404 or 410, it issues an `UPDATE document` (keeping the row and linking `last_crawl_target_id`), deletes the document's `search_index` row, never runs `DELETE FROM document`, and still completes the target. |
| `test_successful_observation_restores_document_availability` | `upsert_document` returns the document ID and its SQL resets `is_available`, `unavailable_at`, and `unavailable_http_status`, so a page that comes back becomes available again. |

## test_deadlock_retry.py

Pytest tests for `jobs.retry_deadlocked_finalization`, with `sleep` and jitter mocked.

| Test | What it checks |
| --- | --- |
| `test_deadlock_retries_fresh_operation_without_refetch` | Two deadlocks (SQLSTATE `40P01`) followed by success give 3 calls in total, with backoff sleeps of 0.2 s and 0.4 s, and return the result. |
| `test_deadlock_exhaustion_propagates_last_error` | Constant deadlocks stop after 4 attempts and re-raise the last `DBAPIError`. |
| `test_other_database_errors_and_cancellation_are_not_retried` | A unique violation (`23505`) or `CancelledError` is raised after one attempt with no retry. |

## test_monitoring.py

Network-free regression tests for pipeline checkpoints, storage events, and the authenticated crawler report API. Uses a fake session that compiles every statement for PostgreSQL to catch SQL mistakes.

| Test | What it checks |
| --- | --- |
| `test_real_parser_pipeline_checkpoints` (8 scenarios) | Runs `process_job` with a mocked fetch for `stored`, `noindex` (via `X-Robots-Tag`), `http404`, `mime` (PDF), `parse_error`, `blocked` (policy `DENY`), `not_modified` (304), and `store_error`. The first checkpoint is always `FETCH running`; `fetch_success` is false only for 404 and blocked; stored pages are parsed and accepted with a `PARSE` checkpoint; noindex is skipped with reason `noindex`; parse errors are tagged `error_category: parse`; the wrong MIME type reports `unsupported MIME`; and a storage failure records `STORE failed` with `stored: 0`, re-raises, and calls `recover_failed_claim`. |
| `test_atomic_storage_events_and_dedup` (5 decisions) | `_finalize` emits a `DEDUP` event with outcome `new`, `unchanged`, `updated`, or `duplicate` (with `matching_document_id`), saves one document, and records the stored document ID in the `STORE` event. With a `stale` (expired) lease, nothing is upserted and the outcome is `stale`. |
| `test_telemetry_failure_does_not_fail_crawl` | `checkpoint` swallows a broken session factory instead of raising. |
| `test_monitoring_routes_enforce_auth_and_validate_filters` | `/admin/crawler/monitor`, `/documents/1`, and `/attempts/1` return 401 without the bearer key and never reach the handler. With the key, `days=0` and an unknown `status` return 422, and a valid request returns 200 with `Cache-Control: private, no-store`, passes `source_id` through, and runs in a `READ ONLY` transaction. |

## test_recovery.py

Network-free pytest tests for lease and attempt recovery.

| Test | What it checks |
| --- | --- |
| `test_abandoned_attempt_is_terminal_and_preserves_original_failure_category` | `close_abandoned_attempts` marks an open attempt `failed` with `finished_at` set, keeps the original `error_category` (`persistence`), emits a `failed` event, and filters by the exact `lease_until`. |
| `test_recovery_never_requeues_a_newer_workers_claim` | If the target now has a newer lease, `recover_failed_claim` does not call `fail_target` and only closes attempts for the old lease (`include_legacy=False`). |
| `test_owned_failure_uses_scheduler_backoff` | If the worker still owns the lease, `recover_failed_claim` calls `fail_target` with that lease. |
| `test_expired_leases_increment_failures_delay_retries_and_reconcile_orphans` | `recover_expired_leases` increments `failure_count` (1 to 2), schedules the retry 120 s out, requeues and clears the lease, closes attempts for both the expired target and an orphaned queued target, uses `SKIP LOCKED`, and filters orphans by `state !=`. |
| `test_timeout_records_exact_claim_and_is_counted_as_failed` | When a job exceeds `job_timeout_seconds`, `execute_target` counts it as both failed and timed out and records the failure for that exact target. |

## test_postgres_pipeline.py

PostgreSQL regression tests. They are skipped unless `TEST_DATABASE_URL` is set, and fail if it is not `postgresql+asyncpg` with `test` in the database name. Each test creates its own source (`max_depth: 3`, `max_pages: 7`) and deletes all its rows afterwards. `PolicyCoordinator.fetch` is mocked.

| Test | What it checks |
| --- | --- |
| `test_structured_resources_commit_documents_targets_and_attempts` (sitemap, rss, api) | Processing a sitemap, RSS feed, or JSON API target succeeds and enqueues one link. Sitemaps save no document and enqueue a `page` child at depth 0; RSS and API save one document (with `ingestion_format` `rss` or `json_api`) and enqueue a same-kind child (the next page) at depth 1. The attempt is finished with `resource_kind` telemetry, and `inspect_document` can read the document. |
| `test_concurrent_claims_atomic_writes_and_shared_source_budget` | Two concurrent claims of 2 get disjoint targets. Processing all 4 concurrently succeeds, saves 4 documents, leaves no open attempts, and caps total targets at the source's `max_pages` of 7 even though each page links to 4 more. `build_monitor` reports 4 attempted and 4 persisted, and the document detail is available. |
| `test_removed_page_invalidates_index_and_recovers_when_restored` | After a 200 then a 404, the document is marked unavailable with status 404 and its search index row is removed. A later 200 makes it available again with no status. |
| `test_expiration_and_old_worker_recovery_do_not_touch_new_claims` | Recovering an old worker's claim and expired leases fails the old attempts, leaves the newer active attempt open, gives the expired target a failure and a future retry, and leaves the newer lease untouched. |

## test_live_pipeline.py

A live, rollback-only script (`python -m crawler.worker.tests.test_live_pipeline`). It is not a pytest test. It runs `PolicyCoordinator -> HTTPXHopFetcher -> parser -> processor` against real URLs (by default five `docs.python.org` pages, or `--url` / `--allow-host`), with one request per host and a 2 s interval. It prints the policy decision, redirect chain, parsed documents, processing results, and a sample of discovered links (never enqueued), and applies `X-Robots-Tag` headers for this bot or `*`. It needs `DATABASE_URL` for the robots cache, rolls the session back, and writes no documents, targets, or index rows. It exits `0` only if at least one document was accepted and there were no errors.
