# Tech docs: why Developer's Eye is built this way

These records preserve decisions, architecture, rejected approaches, experiments, incidents and future optimization targets for senior engineers and AI agents. Mechanics belong beside the code in `docs/` and package guides. This index covers the repository through **2026-11-02, commit `facd333`**.

## Start here

- [Current architecture and integration status](infra/system-architecture/architecture.md)
- [Decision history and abandoned directions](infra/system-architecture/decision-history.md)
- [Historical test reports and fix-log evidence](infra/system-architecture/evidence-catalog.md)
- [All ADRs, incidents and experiments](record-index.md)
- [Optimization targets and measurement gates](infra/performance-and-scaling/optimization-plan.md)
- [Evidence, scope and validation](evidence-and-validation.md)
- [Journal: faced problems, fix log, test reports, glossary](journal/README.md)

## How to read status

“Implemented” means source exists. “Connected” means the inspected caller uses it. Neither proves production deployment. New BM25 statistics/types, query planning, merge and snippets are components; the public API still uses the earlier FTS service. BM25 scoring is unfinished; fuzzy imports and vocabulary maintenance have open defects. Proposals remain proposals even when their configuration types exist.

Existing accepted ADRs are preserved. New retrospective alternatives are engineering comparisons unless a commit, prototype or benchmark proves they were actually tried. No production traffic, corpus size, latency, deployment or quality result is invented from screenshots, commit messages or earlier plans.

## Templates and maintenance rules

Use the existing [decision](_templates/decision.md), [incident](_templates/incident.md), [experiment](_templates/experiment.md) and [feature overview](_templates/feature-overview.md) templates. Records live at `<area>/<feature>/<type>-<global-number>-<slug>.md`.

1. IDs are globally unique per type. Check the record index before choosing the next number.
2. Do not rewrite an accepted decision to erase history. Write a successor ADR and update supersession metadata when behavior changes.
3. List governed code paths and link evidence. Add an enforcement-point record reference when modifying governed runtime code; this retrospective documentation PR does not scatter comments through otherwise unchanged application files.
4. Update the owning feature overview and global record index with each new record.
5. Label planned work, unrun experiments, inferred rationale and historical measured results explicitly.
6. Keep feature overviews current. Read their accepted decisions and incidents before editing a subsystem.
7. Use the navigation generator for its marked blocks; validate local links and template fields before publishing.

## Feature catalog

| Area / feature | Source-level status | Entry point |
| --- | --- | --- |
| infra/system-architecture | active | [System architecture and implementation status](infra/system-architecture/overview.md) |
| crawler/seed-and-discovery | active | [Seeds and discovery](crawler/seed-and-discovery/overview.md) |
| crawler/url-frontier | active | [URL frontier and crawl scope](crawler/url-frontier/overview.md) |
| crawler/scheduler-and-leases | active | [Scheduler and leases](crawler/scheduler-and-leases/overview.md) |
| crawler/url-safety | active | [URL safety and pinned transport](crawler/url-safety/overview.md) |
| crawler/robots-and-politeness | active | [Robots and politeness](crawler/robots-and-politeness/overview.md) |
| crawler/fetcher | active | [Bounded fetcher](crawler/fetcher/overview.md) |
| crawler/parser | active | [HTML and structured resource parsing](crawler/parser/overview.md) |
| crawler/content-processing | active | [Content normalization, classification and fingerprints](crawler/content-processing/overview.md) |
| crawler/document-writer | active | [Document persistence and availability](crawler/document-writer/overview.md) |
| crawler/worker-runtime | active | [Worker lifecycle and recovery](crawler/worker-runtime/overview.md) |
| crawler/monitoring-and-telemetry | active | [Crawler telemetry](crawler/monitoring-and-telemetry/overview.md) |
| indexer/freshness-selection | active | [Freshness-derived index work](indexer/freshness-selection/overview.md) |
| indexer/document-analysis | active | [Document snapshots and weighted fields](indexer/document-analysis/overview.md) |
| indexer/search-vectors | active | [Weighted PostgreSQL text and code vectors](indexer/search-vectors/overview.md) |
| indexer/index-writer | active | [Index writer consistency](indexer/index-writer/overview.md) |
| indexer/reindex-and-versioning | active | [Reindex and index format versioning](indexer/reindex-and-versioning/overview.md) |
| indexer/vocubulary | active | [Fuzzy vocabulary and repair](indexer/vocubulary/overview.md) |
| indexer/coverage-reporting | active | [Index and vocabulary coverage reporting](indexer/coverage-reporting/overview.md) |
| backend/database-schema | active | [Database schema and migrations](backend/database-schema/overview.md) |
| backend/package-boundary | active | [Backend and worker package boundary](backend/package-boundary/overview.md) |
| backend/search-api | active | [Public search API and integration boundary](backend/search-api/overview.md) |
| backend/admin-api | active | [Read-only admin API](backend/admin-api/overview.md) |
| backend/query-planning | active | [Query analysis and explicit retrieval planning](backend/query-planning/overview.md) |
| backend/retrieval | active | [Text and code candidate retrieval](backend/retrieval/overview.md) |
| backend/fuzzy-correction | planned | [Conservative fuzzy correction](backend/fuzzy-correction/overview.md) |
| backend/merge-and-contracts | active | [Candidate merge and data contracts](backend/merge-and-contracts/overview.md) |
| backend/bm25-statistics | active | [BM25 statistics component](backend/bm25-statistics/overview.md) |
| backend/ranking | planned | [BM25 ranking plan](backend/ranking/overview.md) |
| backend/snippets | active | [Query-aware snippets](backend/snippets/overview.md) |
| frontend/search-experience | active | [Public search, code preview and local saves](frontend/search-experience/overview.md) |
| frontend/admin-auth | active | [Admin authentication](frontend/admin-auth/overview.md) |
| frontend/admin-console | active | [Admin console and server proxy](frontend/admin-console/overview.md) |
| frontend/landing-eye | active | [Progressive landing visuals](frontend/landing-eye/overview.md) |
| frontend/api-docs-page | active | [Public API documentation page](frontend/api-docs-page/overview.md) |
| infra/configuration-and-secrets | active | [Configuration and secret handling](infra/configuration-and-secrets/overview.md) |
| infra/local-dev-and-testing | active | [Local development and validation tiers](infra/local-dev-and-testing/overview.md) |
| infra/ci-and-containers | planned | [CI and container plan](infra/ci-and-containers/overview.md) |
| infra/docs-navigation | active | [Documentation layers and navigation](infra/docs-navigation/overview.md) |
| infra/performance-and-scaling | planned | [Optimization and scaling plan](infra/performance-and-scaling/overview.md) |

<!-- docs-nav:start -->
## Documentation map

Every project doc, grouped by area. Generated by `scripts/update_docs_nav.py`; edit that script, not this list.

**Start here**

- [Project overview](../README.md) `README.md`
- [Technical handoff](../technical_handoff.md) `technical_handoff.md`

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
- [Snippet engine](../backend/src/backend/search/snippets/docs/README.md) `backend/src/backend/search/snippets/docs/README.md`
- [Snippet Engine](../backend/src/backend/search/snippets/docs/snippets_docs.md) `backend/src/backend/search/snippets/docs/snippets_docs.md`
- [Backend test cases](../backend/tests/test_case.md) `backend/tests/test_case.md`

**Crawler: seeds and frontier**

- [Crawler package](../crawler/src/crawler/README.md) `crawler/src/crawler/README.md`
- [Sitemap Discovery and Worker Jobs](../crawler/src/crawler/seed/docs/sitemap_discovery.md) `crawler/src/crawler/seed/docs/sitemap_discovery.md`
- [Seed guide](../crawler/src/crawler/seed/guide.md) `crawler/src/crawler/seed/guide.md`
- [Seed list](../crawler/src/crawler/seed/seed_list.md) `crawler/src/crawler/seed/seed_list.md`
- [Developers Eye — Source Registry Seed Plan](../crawler/src/crawler/seed/seed_listing_plan.md) `crawler/src/crawler/seed/seed_listing_plan.md`
- [Scheduler repository and target states](../crawler/src/crawler/scheduler/docs/REPOSITORY_README.md) `crawler/src/crawler/scheduler/docs/REPOSITORY_README.md`
- [Scheduler concepts to note](../crawler/src/crawler/scheduler/docs/new_concept_to_note.md) `crawler/src/crawler/scheduler/docs/new_concept_to_note.md`

**Crawler: fetch and policy**

- [Developer's Eye: Async Fetcher — Full Flow](../crawler/src/crawler/fetcher/docs/flow.md) `crawler/src/crawler/fetcher/docs/flow.md`
- [Policy components overview](../crawler/src/crawler/policy_and_politeness/README.md) `crawler/src/crawler/policy_and_politeness/README.md`
- [Host Policy](../crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md) `crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md`
- [DNS/IP Policy & Safe HTTP Transport](../crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md) `crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md`
- [Robots Policy. Third step of our crawler safety checks](../crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md) `crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md`
- [Politeness Policy. Fourth step of our crawler safety checks](../crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md) `crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md`
- [Redirect Policy: What if a website sends our crawler somewhere else?](../crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md) `crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md`
- [Avengers assemble. Policy Coordinator. Final step of our crawler policy phase](../crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md) `crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md`
- [Policy docs introduction](../crawler/src/crawler/policy_and_politeness/docs/README.md) `crawler/src/crawler/policy_and_politeness/docs/README.md`

**Crawler: parse, process, write**

- [JSON API Ingestion](../crawler/src/crawler/parser/docs/json_api.md) `crawler/src/crawler/parser/docs/json_api.md`
- [Developer's Eye: Parser Engine](../crawler/src/crawler/parser/docs/parser.md) `crawler/src/crawler/parser/docs/parser.md`
- [RSS and Atom Feed Ingestion](../crawler/src/crawler/parser/docs/rss_atom.md) `crawler/src/crawler/parser/docs/rss_atom.md`
- [XML Sitemap Parser](../crawler/src/crawler/parser/docs/sitemap.md) `crawler/src/crawler/parser/docs/sitemap.md`
- [Classifier Model](../crawler/src/crawler/processing/docs/classifier.md) `crawler/src/crawler/processing/docs/classifier.md`
- [content processing pipeline](../crawler/src/crawler/processing/docs/content_processing.md) `crawler/src/crawler/processing/docs/content_processing.md`
- [Fingerprint Model](../crawler/src/crawler/processing/docs/fingerprint.md) `crawler/src/crawler/processing/docs/fingerprint.md`
- [Normalizer Model](../crawler/src/crawler/processing/docs/normalize.md) `crawler/src/crawler/processing/docs/normalize.md`
- [Processor Model](../crawler/src/crawler/processing/docs/processor_model.md) `crawler/src/crawler/processing/docs/processor_model.md`
- [Developer's Eye: Database Writer](../crawler/src/crawler/writer/docs/developers_eye_writer_docs.md) `crawler/src/crawler/writer/docs/developers_eye_writer_docs.md`

**Crawler: worker and ingestion**

- [Worker Jobs — Developer's Eye](../crawler/src/crawler/worker/docs/jobs_docs.md) `crawler/src/crawler/worker/docs/jobs_docs.md`
- [Runner.py — Developer's Eye Crawler Worker](../crawler/src/crawler/worker/docs/runner_docs.md) `crawler/src/crawler/worker/docs/runner_docs.md`
- [Testing Crawler Ingestion](../crawler/tests/README.md) `crawler/tests/README.md`
- [Crawler test cases](../crawler/tests/test_case.md) `crawler/tests/test_case.md`

**Indexer**

- [Developer's Eye indexer service + writer](../crawler/src/indexer/README.md) `crawler/src/indexer/README.md`
- [Developer's Eye: Indexer Analyzer](../crawler/src/indexer/docs/ANALYZER.md) `crawler/src/indexer/docs/ANALYZER.md`
- [ADR: Maintain Developer's Eye Vocabulary Consistency in the Existing Indexer](../crawler/src/indexer/docs/adr-vocabulary-consistency-pr4.md) `crawler/src/indexer/docs/adr-vocabulary-consistency-pr4.md`
- [Developer's Eye — Indexer: Builder](../crawler/src/indexer/docs/builder.md) `crawler/src/indexer/docs/builder.md`
- [Indexer configuration](../crawler/src/indexer/docs/config.md) `crawler/src/indexer/docs/config.md`
- [Indexer file responsibilities](../crawler/src/indexer/docs/file_task.md) `crawler/src/indexer/docs/file_task.md`
- [Pr#3-vocubulary-fixes](../crawler/src/indexer/docs/pr%233-vocubulary-fixes.md) `crawler/src/indexer/docs/pr#3-vocubulary-fixes.md`
- [Developer's Eye: Vocabulary Consistency (PR #4)](../crawler/src/indexer/docs/pr4-vocabulary-consistency.md) `crawler/src/indexer/docs/pr4-vocabulary-consistency.md`
- [reporting.py — indexer coverage report](../crawler/src/indexer/docs/reporting.md) `crawler/src/indexer/docs/reporting.md`
- [Developer's Eye — Indexer: Selector](../crawler/src/indexer/docs/selector.md) `crawler/src/indexer/docs/selector.md`
- [Developer's Eye: Indexer service](../crawler/src/indexer/docs/service.md) `crawler/src/indexer/docs/service.md`
- [Developer's Eye: vector.py](../crawler/src/indexer/docs/vector.md) `crawler/src/indexer/docs/vector.md`
- [Developer's Eye: Transactional index writer](../crawler/src/indexer/docs/writer.md) `crawler/src/indexer/docs/writer.md`
- [Developer's Eye indexer operations](../crawler/src/indexer/operations.md) `crawler/src/indexer/operations.md`

**Frontend (Next.js, admin)**

- [Developer’s Eye frontend](../frontend/README.md) `frontend/README.md`
- [Developer’s Eye — API and backend connector reference](../frontend/public/api-reference.md) `frontend/public/api-reference.md`
- [Running the frontend tests](../frontend/tests/README.md) `frontend/tests/README.md`
- [Frontend test cases](../frontend/tests/test_case.md) `frontend/tests/test_case.md`

**Other**

- [All test cases that were tested](../tests/all-test-cases-that-were-tested/index.md) `tests/all-test-cases-that-were-tested/index.md`
- [Test index of the whole app](../tests/test-index-of-whole-app.md) `tests/test-index-of-whole-app.md`
<!-- docs-nav:end -->
