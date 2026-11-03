# Historical evidence catalog

These retained reports and fix logs complement the ADR/INC/EXP records. They describe their original checks and environments; this PR did not rerun those historical sessions. Test authorship, a report of a past pass and current passing CI are different forms of evidence.

## Earlier component verification

| Source | What it preserves | Limit |
| --- | --- | --- |
| [First database-writer report](../../journal/test-reports/writer-first-successful-test.md) | October 19 report: package/export/interface mismatches, database insert/update/rollback checks; reported 7 passed in 1.00 second | Writer-to-database checks, explicitly not the full HTTP crawler; not current runtime performance |
| [Early scheduler report](../../journal/test-reports/scheduler-test-1-report.md) | Initial claim/complete/fail/recovery contract and test sequence | Predates round-robin changes and later concurrent tests; its remaining-work checklist is historical |
| [Claim concurrency benchmark](../../crawler/scheduler-and-leases/EXP-0001-claim-path-concurrency-benchmark.md) | Declared machine/workload, source-lock comparison, latency and drain throughput | Historical synthetic benchmark, not rerun and not production QPS |
| [Structured-ingestion verification](../../journal/update-log/18_structured_ingestion_edges.md) | Reported 456 offline tests and 33 subtests, six DB skips in the offline run, 13 PostgreSQL persistence tests and 73 DNS checks | Specific historical session on a separate PostgreSQL 18 cluster; not a guarantee for every supported PostgreSQL version |
| [Indexer test guide](../../../crawler/src/indexer/tests/README.md) | Test inventory and environment requirements | Describes how to run; does not certify the current test outcome |
| [Snippet PR #6](https://github.com/nishchup489-afk/developers_eye/pull/6) | Budget fix, authored regressions and docs | PR states those tests were not executed in that session |
| [Vocabulary PR #4](https://github.com/nishchup489-afk/developers_eye/pull/4) | Forward schema repair, shared removals, rebuild and tests | PR states live PostgreSQL/CI verification was not run; current defects remain documented |

## Crawler fix-log cross-reference

| Log | Lesson / owning record |
| --- | --- |
| [Fixing HTTP transport error handling](../../journal/update-log/01_transport_errors.md) | Exception conversion preserves original failure; INC-0010 |
| [Fixing fetcher policy rejections](../../journal/update-log/02_policy_rejections.md) | Shared policy exception identity; INC-0010 |
| [Fixing pinned HTTP request validation](../../journal/update-log/03_pinned_requests.md) | Pin the exact approved URL/Host/TLS identity; INC-0005 |
| [Fixing robots.txt matching](../../journal/update-log/04_robots_rules.md) | Wildcard and longest-match robots semantics; INC-0004 |
| [Fixing combined robots metadata](../../journal/update-log/05_robots_metadata.md) | Combine all applicable robots metadata; INC-0012 |
| [Connecting the deadlock retry helper](../../journal/update-log/06_deadlock_retry.md) | A retry helper must be called around the replayable transaction; INC-0002 |
| [Enforcing crawl depth and source budgets](../../journal/update-log/07_crawl_scope.md) | Scope configuration needs enforced insertion boundaries; INC-0003 |
| [Fixing abandoned attempts and retry recovery](../../journal/update-log/08_failure_recovery.md) | Lease-owned attempt closure and normal backoff; INC-0011 |
| [Fixing stored content after 404 and 410 responses](../../journal/update-log/09_content_availability.md) | Soft availability and index cleanup; ADR-0011 |
| [Fixing machine-specific and circular package dependencies](../../journal/update-log/10_portable_packages.md) | Relative dependencies and one-way package boundary; ADR-0012 |
| [Verifying the fixes against PostgreSQL](../../journal/update-log/11_postgres_regressions.md) | Real PostgreSQL regression evidence is distinct from mocks; ADR-0035 |
| [Cleaning the frontier model whitespace](../../journal/update-log/12_frontier_whitespace.md) | Repository hygiene; no separate architecture decision claimed |
| [Resolving the remaining merge conflicts](../../journal/update-log/13_merge_conflicts.md) | Preserve both histories and inspect conflict resolution; no measured performance claim |
| [Completing XML sitemap parsing](../../journal/update-log/14_sitemap_parser.md) | Bounded XML resource adapter; ADR-0018 |
| [Wiring sitemap discovery into the worker](../../journal/update-log/15_sitemap_discovery.md) | Sitemap discovery reuses the worker/frontier; ADR-0014 |
| [Adding RSS and Atom ingestion](../../journal/update-log/16_rss_atom_ingestion.md) | RSS/Atom entries use shared ingestion; ADR-0018 |
| [Adding configurable JSON API ingestion](../../journal/update-log/17_json_api_ingestion.md) | Mapped JSON API records and pagination; ADR-0018 |
| [Closing structured-ingestion edge cases and verifying persistence](../../journal/update-log/18_structured_ingestion_edges.md) | Compressed sitemap MIME, Atom XHTML cleanup, malformed values and seed reservation; ADR-0014/0018 |
| [Reconciling the local and remote ingestion histories](../../journal/update-log/19_ingestion_history_merge.md) | Merge the actual local/remote histories and preserve unique changes; compare both parents |

## Interpretation rules

Use current source plus the newer feature overview for present behavior. Preserve original reports as historical evidence; do not silently rewrite their results to match a new environment. A separate benchmark protocol is required before deriving speed, scale or production readiness from a functional test count.
