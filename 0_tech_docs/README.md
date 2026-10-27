# Tech docs (why the system is built this way)

These docs record **why**: decisions, the algorithms we chose and rejected, and the incidents that taught us something. They are written for senior engineers and AI agents who need to change the system without repeating old mistakes. **How** the code works lives next to the code (`*/docs/`, package READMEs); start at `technical_handoff.md` for the overall picture.

## Layout

```
0_tech_docs/
  _templates/                 copy from here, never edit in place
  <area>/<feature>/
    overview.md               purpose, code, record index, rules for future changes
    ADR-0001-<slug>.md        a decision
    INC-0001-<slug>.md        an incident (disaster log)
    EXP-0001-<slug>.md        an experiment or benchmark
```

Areas: `crawler`, `indexer`, `backend`, `frontend`, `infra`. A record that spans features lives in the feature that owns the change and is linked from the others.

## Rules

1. **Numbers are global per type** (`ADR-0007` is unique across the repo). Take the next free number: `ls 0_tech_docs/*/*/ADR-* | sort | tail -1`.
2. **Accepted ADRs are not rewritten.** To change a decision, write a new ADR with `supersedes: ADR-000N` and set the old one to `superseded`.
3. **Every record lists the code it governs** in its front matter (`code:`). Put `# ADR-000N` (or `// ADR-000N`) in a comment on the line that enforces the decision so a reader of the code can find the reason.
4. **Separate measured facts from assumptions.** Link the test, log, benchmark or commit.
5. **Update the feature's `overview.md`** (records table, rules for future changes) in the same commit as the record.
6. Keep records short. A decision that needs more than two pages is probably two decisions.

## For AI agents

Before changing a feature: read its `overview.md`, then every `accepted` ADR and every INC it lists. Do not break a rule under "Rules for future changes" without writing a new ADR. When you fix a non-trivial bug, add an INC record.

## Features

### Crawler (`crawler/src/crawler`)

| Feature | Folder |
| --- | --- |
| [Seeds and discovery](crawler/seed-and-discovery/overview.md) | `crawler/seed-and-discovery/` |
| [URL frontier and crawl scope](crawler/url-frontier/overview.md) | `crawler/url-frontier/` |
| [Scheduler and leases](crawler/scheduler-and-leases/overview.md) | `crawler/scheduler-and-leases/` |
| [URL safety (SSRF, DNS, redirects)](crawler/url-safety/overview.md) | `crawler/url-safety/` |
| [Robots.txt and politeness](crawler/robots-and-politeness/overview.md) | `crawler/robots-and-politeness/` |
| [Fetcher](crawler/fetcher/overview.md) | `crawler/fetcher/` |
| [Parser (HTML, sitemaps, feeds, JSON APIs)](crawler/parser/overview.md) | `crawler/parser/` |
| [Content processing](crawler/content-processing/overview.md) | `crawler/content-processing/` |
| [Document and attempt writer](crawler/document-writer/overview.md) | `crawler/document-writer/` |
| [Worker runtime](crawler/worker-runtime/overview.md) | `crawler/worker-runtime/` |
| [Monitoring and telemetry](crawler/monitoring-and-telemetry/overview.md) | `crawler/monitoring-and-telemetry/` |

### Indexer (`crawler/src/indexer`)

| Feature | Folder |
| --- | --- |
| [Freshness selection (no queue)](indexer/freshness-selection/overview.md) | `indexer/freshness-selection/` |
| [Document snapshot and field weighting](indexer/document-analysis/overview.md) | `indexer/document-analysis/` |
| [Search vectors](indexer/search-vectors/overview.md) | `indexer/search-vectors/` |
| [Index writer consistency](indexer/index-writer/overview.md) | `indexer/index-writer/` |
| [Reindex and index versioning](indexer/reindex-and-versioning/overview.md) | `indexer/reindex-and-versioning/` |
| [Coverage reporting](indexer/coverage-reporting/overview.md) | `indexer/coverage-reporting/` |

### Backend API and database (`backend/`)

| Feature | Folder |
| --- | --- |
| [Database schema and migrations](backend/database-schema/overview.md) | `backend/database-schema/` |
| [Read-only admin API](backend/admin-api/overview.md) | `backend/admin-api/` |
| [Backend and crawler package boundary](backend/package-boundary/overview.md) | `backend/package-boundary/` |
| [Search API (planned)](backend/search-api/overview.md) | `backend/search-api/` |

### Frontend (`frontend/`)

| Feature | Folder |
| --- | --- |
| [Landing page and animated eye](frontend/landing-eye/overview.md) | `frontend/landing-eye/` |
| [Search experience and demo mode](frontend/search-experience/overview.md) | `frontend/search-experience/` |
| [Public API docs page](frontend/api-docs-page/overview.md) | `frontend/api-docs-page/` |
| [Admin authentication](frontend/admin-auth/overview.md) | `frontend/admin-auth/` |
| [Admin console and backend proxy](frontend/admin-console/overview.md) | `frontend/admin-console/` |

### Configuration, tooling and operations

| Feature | Folder |
| --- | --- |
| [Configuration and secrets](infra/configuration-and-secrets/overview.md) | `infra/configuration-and-secrets/` |
| [Local development and testing](infra/local-dev-and-testing/overview.md) | `infra/local-dev-and-testing/` |
| [CI and containers (planned)](infra/ci-and-containers/overview.md) | `infra/ci-and-containers/` |
| [Docs navigation](infra/docs-navigation/overview.md) | `infra/docs-navigation/` |

<!-- docs-nav:start -->
## Documentation map

Every project doc, grouped by area. Generated by `scripts/update_docs_nav.py`; edit that script, not this list.

**Start here**

- [Project overview](../README.md) `README.md`
- [Technical handoff](../technical_handoff.md) `technical_handoff.md`
- [Developers Eye — Complete Engineering Checklist](../crawler/DEVELOPERS_EYE_CHECKLIST.md) `crawler/DEVELOPERS_EYE_CHECKLIST.md`

**Tech docs (why)**

- [Tech docs index (decisions, incidents, experiments)](README.md) `0_tech_docs/README.md` (you are here)

**Backend (FastAPI, database)**

- [Developer's Eye backend](../backend/README.md) `backend/README.md`
- [Table notes: crawl_attempt](../backend/docs/db/crawl_attempt.md) `backend/docs/db/crawl_attempt.md`
- [Table notes: crawler_frontier](../backend/docs/db/crawler_frontier.md) `backend/docs/db/crawler_frontier.md`
- [Table notes: documents](../backend/docs/db/documents.md) `backend/docs/db/documents.md`
- [Table notes: robot](../backend/docs/db/robot.md) `backend/docs/db/robot.md`
- [Table notes: search_index](../backend/docs/db/search_index.md) `backend/docs/db/search_index.md`
- [Table notes: source](../backend/docs/db/source.md) `backend/docs/db/source.md`

**Crawler: seeds and frontier**

- [Crawler package](../crawler/src/crawler/README.md) `crawler/src/crawler/README.md`
- [Sitemap Discovery and Worker Jobs](../crawler/src/crawler/seed/docs/sitemap_discovery.md) `crawler/src/crawler/seed/docs/sitemap_discovery.md`
- [Seed guide](../crawler/src/crawler/seed/guide.md) `crawler/src/crawler/seed/guide.md`
- [Seed list](../crawler/src/crawler/seed/seed_list.md) `crawler/src/crawler/seed/seed_list.md`
- [Developers Eye — Source Registry Seed Plan](../crawler/src/crawler/seed/seed_listing_plan.md) `crawler/src/crawler/seed/seed_listing_plan.md`
- [Running the frontier tests](../crawler/src/crawler/frontier/tests/README.md) `crawler/src/crawler/frontier/tests/README.md`
- [Frontier test cases](../crawler/src/crawler/frontier/tests/test_case.md) `crawler/src/crawler/frontier/tests/test_case.md`
- [Scheduler repository and target states](../crawler/src/crawler/schedular/DOCS/REPOSITORY_README.md) `crawler/src/crawler/schedular/DOCS/REPOSITORY_README.md`
- [Scheduler concepts to note](../crawler/src/crawler/schedular/DOCS/new_concept_to_note.md) `crawler/src/crawler/schedular/DOCS/new_concept_to_note.md`
- [Running the scheduler tests](../crawler/src/crawler/schedular/tests/README.md) `crawler/src/crawler/schedular/tests/README.md`
- [Developers Eye — Scheduler Tests](../crawler/src/crawler/schedular/tests/test1_report.md) `crawler/src/crawler/schedular/tests/test1_report.md`
- [Schedular test cases](../crawler/src/crawler/schedular/tests/test_case.md) `crawler/src/crawler/schedular/tests/test_case.md`

**Crawler: fetch and policy**

- [Developer's Eye: Async Fetcher — Full Flow](../crawler/src/crawler/fetcher/docs/flow.md) `crawler/src/crawler/fetcher/docs/flow.md`
- [Developer's Eye fetcher tests](../crawler/src/crawler/fetcher/tests/fetcher_tests/README.md) `crawler/src/crawler/fetcher/tests/fetcher_tests/README.md`
- [Policy components overview](../crawler/src/crawler/policy_and_politeness/README.md) `crawler/src/crawler/policy_and_politeness/README.md`
- [Host Policy](../crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md) `crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md`
- [DNS/IP Policy & Safe HTTP Transport](../crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md) `crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md`
- [Robots Policy. Third step of our crawler safety checks](../crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md) `crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md`
- [Politeness Policy. Fourth step of our crawler safety checks](../crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md) `crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md`
- [Redirect Policy: What if a website sends our crawler somewhere else?](../crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md) `crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md`
- [Avengers assemble. Policy Coordinator. Final step of our crawler policy phase](../crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md) `crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md`
- [Policy docs introduction](../crawler/src/crawler/policy_and_politeness/docs/README.md) `crawler/src/crawler/policy_and_politeness/docs/README.md`
- [Running the policy and politeness tests](../crawler/src/crawler/policy_and_politeness/tests/README.md) `crawler/src/crawler/policy_and_politeness/tests/README.md`
- [Policy and politeness test cases](../crawler/src/crawler/policy_and_politeness/tests/test_case.md) `crawler/src/crawler/policy_and_politeness/tests/test_case.md`

**Crawler: parse, process, write**

- [JSON API Ingestion](../crawler/src/crawler/parser/docs/json_api.md) `crawler/src/crawler/parser/docs/json_api.md`
- [Developer's Eye: Parser Engine](../crawler/src/crawler/parser/docs/parser.md) `crawler/src/crawler/parser/docs/parser.md`
- [RSS and Atom Feed Ingestion](../crawler/src/crawler/parser/docs/rss_atom.md) `crawler/src/crawler/parser/docs/rss_atom.md`
- [XML Sitemap Parser](../crawler/src/crawler/parser/docs/sitemap.md) `crawler/src/crawler/parser/docs/sitemap.md`
- [Running the parser tests](../crawler/src/crawler/parser/tests/README.md) `crawler/src/crawler/parser/tests/README.md`
- [Parser test cases](../crawler/src/crawler/parser/tests/test_case.md) `crawler/src/crawler/parser/tests/test_case.md`
- [Classifier Model](../crawler/src/crawler/processing/docs/classifier.md) `crawler/src/crawler/processing/docs/classifier.md`
- [content processing pipeline](../crawler/src/crawler/processing/docs/content_processing.md) `crawler/src/crawler/processing/docs/content_processing.md`
- [Fingerprint Model](../crawler/src/crawler/processing/docs/fingerprint.md) `crawler/src/crawler/processing/docs/fingerprint.md`
- [Normalizer Model](../crawler/src/crawler/processing/docs/normalize.md) `crawler/src/crawler/processing/docs/normalize.md`
- [Processor Model](../crawler/src/crawler/processing/docs/processor_model.md) `crawler/src/crawler/processing/docs/processor_model.md`
- [Running the processing tests](../crawler/src/crawler/processing/tests/README.md) `crawler/src/crawler/processing/tests/README.md`
- [Processing test cases](../crawler/src/crawler/processing/tests/test_case.md) `crawler/src/crawler/processing/tests/test_case.md`
- [Developer's Eye: Database Writer](../crawler/src/crawler/writer/docs/developers_eye_writer_docs.md) `crawler/src/crawler/writer/docs/developers_eye_writer_docs.md`
- [Developer's Eye: Database Writer — Debugging & Test Report](../crawler/src/crawler/writer/tests/1st_succuessful_test_report.md) `crawler/src/crawler/writer/tests/1st_succuessful_test_report.md`

**Crawler: worker and ingestion**

- [Worker Jobs — Developer's Eye](../crawler/src/crawler/worker/docs/jobs_docs.md) `crawler/src/crawler/worker/docs/jobs_docs.md`
- [Runner.py — Developer's Eye Crawler Worker](../crawler/src/crawler/worker/docs/runner_docs.md) `crawler/src/crawler/worker/docs/runner_docs.md`
- [Running the worker tests](../crawler/src/crawler/worker/tests/README.md) `crawler/src/crawler/worker/tests/README.md`
- [Worker test cases](../crawler/src/crawler/worker/tests/test_case.md) `crawler/src/crawler/worker/tests/test_case.md`
- [Testing Crawler Ingestion](../crawler/tests/README.md) `crawler/tests/README.md`
- [Crawler test cases](../crawler/tests/test_case.md) `crawler/tests/test_case.md`

**Crawler: fix log**

- [Test run order](../crawler/src/crawler/test/order.md) `crawler/src/crawler/test/order.md`
- [Fixing PostgreSQL Deadlocks in Developer's Eye](../crawler/src/crawler/test/upadte_log/update_10_20_2026_8_39_PM.md) `crawler/src/crawler/test/upadte_log/update_10_20_2026_8_39_PM.md`
- [Fixing HTTP transport error handling](../crawler/src/crawler/test/update_log/01_transport_errors.md) `crawler/src/crawler/test/update_log/01_transport_errors.md`
- [Fixing fetcher policy rejections](../crawler/src/crawler/test/update_log/02_policy_rejections.md) `crawler/src/crawler/test/update_log/02_policy_rejections.md`
- [Fixing pinned HTTP request validation](../crawler/src/crawler/test/update_log/03_pinned_requests.md) `crawler/src/crawler/test/update_log/03_pinned_requests.md`
- [Fixing robots.txt matching](../crawler/src/crawler/test/update_log/04_robots_rules.md) `crawler/src/crawler/test/update_log/04_robots_rules.md`
- [Fixing combined robots metadata](../crawler/src/crawler/test/update_log/05_robots_metadata.md) `crawler/src/crawler/test/update_log/05_robots_metadata.md`
- [Connecting the deadlock retry helper](../crawler/src/crawler/test/update_log/06_deadlock_retry.md) `crawler/src/crawler/test/update_log/06_deadlock_retry.md`
- [Enforcing crawl depth and source budgets](../crawler/src/crawler/test/update_log/07_crawl_scope.md) `crawler/src/crawler/test/update_log/07_crawl_scope.md`
- [Fixing abandoned attempts and retry recovery](../crawler/src/crawler/test/update_log/08_failure_recovery.md) `crawler/src/crawler/test/update_log/08_failure_recovery.md`
- [Fixing stored content after 404 and 410 responses](../crawler/src/crawler/test/update_log/09_content_availability.md) `crawler/src/crawler/test/update_log/09_content_availability.md`
- [Fixing machine-specific and circular package dependencies](../crawler/src/crawler/test/update_log/10_portable_packages.md) `crawler/src/crawler/test/update_log/10_portable_packages.md`
- [Verifying the fixes against PostgreSQL](../crawler/src/crawler/test/update_log/11_postgres_regressions.md) `crawler/src/crawler/test/update_log/11_postgres_regressions.md`
- [Cleaning the frontier model whitespace](../crawler/src/crawler/test/update_log/12_frontier_whitespace.md) `crawler/src/crawler/test/update_log/12_frontier_whitespace.md`
- [Resolving the remaining merge conflicts](../crawler/src/crawler/test/update_log/13_merge_conflicts.md) `crawler/src/crawler/test/update_log/13_merge_conflicts.md`
- [Completing XML sitemap parsing](../crawler/src/crawler/test/update_log/14_sitemap_parser.md) `crawler/src/crawler/test/update_log/14_sitemap_parser.md`
- [Wiring sitemap discovery into the worker](../crawler/src/crawler/test/update_log/15_sitemap_discovery.md) `crawler/src/crawler/test/update_log/15_sitemap_discovery.md`
- [Adding RSS and Atom ingestion](../crawler/src/crawler/test/update_log/16_rss_atom_ingestion.md) `crawler/src/crawler/test/update_log/16_rss_atom_ingestion.md`
- [Adding configurable JSON API ingestion](../crawler/src/crawler/test/update_log/17_json_api_ingestion.md) `crawler/src/crawler/test/update_log/17_json_api_ingestion.md`
- [Closing structured-ingestion edge cases and verifying persistence](../crawler/src/crawler/test/update_log/18_structured_ingestion_edges.md) `crawler/src/crawler/test/update_log/18_structured_ingestion_edges.md`
- [Reconciling the local and remote ingestion histories](../crawler/src/crawler/test/update_log/19_ingestion_history_merge.md) `crawler/src/crawler/test/update_log/19_ingestion_history_merge.md`

**Indexer**

- [Developer's Eye indexer service + writer](../crawler/src/indexer/README.md) `crawler/src/indexer/README.md`
- [Developer's Eye: Indexer Analyzer](../crawler/src/indexer/docs/ANALYZER.md) `crawler/src/indexer/docs/ANALYZER.md`
- [Developer's Eye — Indexer: Builder](../crawler/src/indexer/docs/builder.md) `crawler/src/indexer/docs/builder.md`
- [Indexer configuration](../crawler/src/indexer/docs/config.md) `crawler/src/indexer/docs/config.md`
- [Indexer file responsibilities](../crawler/src/indexer/docs/file_task.md) `crawler/src/indexer/docs/file_task.md`
- [reporting.py — indexer coverage report](../crawler/src/indexer/docs/reporting.md) `crawler/src/indexer/docs/reporting.md`
- [Developer's Eye — Indexer: Selector](../crawler/src/indexer/docs/selector.md) `crawler/src/indexer/docs/selector.md`
- [Developer's Eye: Indexer service](../crawler/src/indexer/docs/service.md) `crawler/src/indexer/docs/service.md`
- [Developer's Eye: vector.py](../crawler/src/indexer/docs/vector.md) `crawler/src/indexer/docs/vector.md`
- [Developer's Eye: Transactional index writer](../crawler/src/indexer/docs/writer.md) `crawler/src/indexer/docs/writer.md`
- [Developer's Eye indexer operations](../crawler/src/indexer/operations.md) `crawler/src/indexer/operations.md`
- [Running the indexer tests](../crawler/src/indexer/tests/README.md) `crawler/src/indexer/tests/README.md`
- [Indexer test cases](../crawler/src/indexer/tests/test_case.md) `crawler/src/indexer/tests/test_case.md`

**Frontend (Next.js, admin)**

- [Developer’s Eye frontend](../frontend/README.md) `frontend/README.md`
- [Developer’s Eye — API and backend connector reference](../frontend/public/api-reference.md) `frontend/public/api-reference.md`
- [Running the frontend tests](../frontend/tests/README.md) `frontend/tests/README.md`
- [Frontend test cases](../frontend/tests/test_case.md) `frontend/tests/test_case.md`

**Other**

- [Faced problems](../crawler/faced_problems.md) `crawler/faced_problems.md`
<!-- docs-nav:end -->
