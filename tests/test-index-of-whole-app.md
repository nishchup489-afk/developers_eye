# Test index of the whole app

This folder is the one place to find every test in Developer's Eye.

```
tests/
├── end-to-end/                          full-app tests (empty for now)
├── test-index-of-whole-app.md           this file: every suite, file and how to run it
└── all-test-cases-that-were-tested/
    └── index.md                         every test case, file by file, plus the write-ups
```

**Why the test files are not moved here.** Each suite stays next to the code it
tests because its runner depends on that location: `backend/` and `crawler/`
each run pytest from their own Poetry project (`testpaths = ["tests"]`, shared
`conftest.py` fixtures), and `frontend/tests/*.mjs` import `../lib/...` and are
wired into `frontend/package.json`. The `test_case.md` write-ups are linked from
`0_tech_docs`, so they stay put as well. This folder indexes all of them.

**Keeping it current.** `python scripts/update_test_index.py` rewrites the
generated part below and `index.md`. Any file whose name starts with `test_`, or
any file under a `test/` or `tests/` folder, is picked up automatically. Run
`python scripts/update_test_index.py --install-hook` once per clone and the
indexes refresh on every commit. `--check` exits 1 when they are stale.

Everything between the markers is generated. Write notes above them.

<!-- test-index:start -->
**89 test files, 724 named test cases** (Python `test_*` functions; script-style `.mjs` files count as one file each).

| Suite | Test files | Named cases | How to run |
|---|---:|---:|---|
| [End-to-end (full app)](#end-to-end-full-app) | 0 | 0 | Not written yet. |
| [Backend (FastAPI, search)](#backend-fastapi-search) | 30 | 292 | `cd backend && poetry run pytest` |
| [Indexer](#indexer) | 13 | 108 | `cd crawler && poetry run pytest tests/indexer` |
| [Crawler](#crawler) | 34 | 324 | `cd crawler && poetry run pytest tests/crawler` |
| [Frontend (Next.js, admin)](#frontend-nextjs-admin) | 12 | 0 | npm scripts in `frontend/package.json` (see below) |

### End-to-end (full app)

Empty for now. Full-app tests go in `tests/end-to-end/`.

### Backend (FastAPI, search)

| File | Kind | Cases | Write-up |
|---|---|---:|---|
| [__init__.py](../backend/tests/__init__.py) | helper |  |  |
| [api/conftest.py](../backend/tests/api/conftest.py) | fixtures |  |  |
| [api/test_search.py](../backend/tests/api/test_search.py) | tests | 8 | [test_case.md](../backend/tests/test_case.md#search-http-api) |
| [api/test_search_limits.py](../backend/tests/api/test_search_limits.py) | tests | 22 | [test_case.md](../backend/tests/test_case.md#public-search-limits-adr-0046) |
| [api/test_search_route.py](../backend/tests/api/test_search_route.py) | tests | 4 | [test_case.md](../backend/tests/test_case.md#search-http-api) |
| [golden/test_bm25_golden.py](../backend/tests/golden/test_bm25_golden.py) | tests | 8 |  |
| [integration/test_code.py](../backend/tests/integration/test_code.py) | tests | 17 | [test_case.md](../backend/tests/test_case.md#code-retrieval) |
| [integration/test_corpus_mutation_search.py](../backend/tests/integration/test_corpus_mutation_search.py) | tests | 4 |  |
| [integration/test_fts.py](../backend/tests/integration/test_fts.py) | tests | 14 | [test_case.md](../backend/tests/test_case.md#full-text-search-fts) |
| [integration/test_fuzzy_suggestions.py](../backend/tests/integration/test_fuzzy_suggestions.py) | tests | 4 | [test_case.md](../backend/tests/test_case.md#fuzzy-suggestions) |
| [integration/test_migrations.py](../backend/tests/integration/test_migrations.py) | tests | 3 |  |
| [integration/test_ranking_developer_queries.py](../backend/tests/integration/test_ranking_developer_queries.py) | tests | 4 |  |
| [integration/test_ranking_statistics.py](../backend/tests/integration/test_ranking_statistics.py) | tests | 8 | [test_case.md](../backend/tests/test_case.md#ranking-statistics-retrieval-postgresql) |
| [integration/test_retrieval.py](../backend/tests/integration/test_retrieval.py) | tests | 6 | [test_case.md](../backend/tests/test_case.md#ranking-statistics-retrieval-postgresql) |
| [integration/test_search.py](../backend/tests/integration/test_search.py) | tests | 5 | [test_case.md](../backend/tests/test_case.md#search-service-against-postgresql) |
| [integration/test_search_deadlines.py](../backend/tests/integration/test_search_deadlines.py) | tests | 3 | [test_case.md](../backend/tests/test_case.md#public-search-limits-adr-0046) |
| [integration/test_search_reporting.py](../backend/tests/integration/test_search_reporting.py) | tests | 9 |  |
| [integration/test_system_reporting.py](../backend/tests/integration/test_system_reporting.py) | tests | 7 | [test_case.md](../backend/tests/test_case.md#admin-system-reporting-postgresql) |
| [test_case.md](../backend/tests/test_case.md) | write-up |  |  |
| [test_package_boundary.py](../backend/tests/test_package_boundary.py) | tests | 1 | [test_case.md](../backend/tests/test_case.md#package-boundary) |
| [unit/test_analyzer.py](../backend/tests/unit/test_analyzer.py) | tests | 13 | [test_case.md](../backend/tests/test_case.md#query-analyzer) |
| [unit/test_corpus_refresh.py](../backend/tests/unit/test_corpus_refresh.py) | tests | 3 |  |
| [unit/test_fuzzy_suggestions.py](../backend/tests/unit/test_fuzzy_suggestions.py) | tests | 9 | [test_case.md](../backend/tests/test_case.md#fuzzy-suggestions) |
| [unit/test_main_lifespan_search.py](../backend/tests/unit/test_main_lifespan_search.py) | tests | 1 | [test_case.md](../backend/tests/test_case.md#app-startup-lifespan) |
| [unit/test_pagination.py](../backend/tests/unit/test_pagination.py) | tests | 3 | [test_case.md](../backend/tests/test_case.md#pagination) |
| [unit/test_planner.py](../backend/tests/unit/test_planner.py) | tests | 11 | [test_case.md](../backend/tests/test_case.md#query-planner) |
| [unit/test_ranking.py](../backend/tests/unit/test_ranking.py) | tests | 26 | [test_case.md](../backend/tests/test_case.md#bm25-formula-and-ranking-types) |
| [unit/test_ranking_orchestrator.py](../backend/tests/unit/test_ranking_orchestrator.py) | tests | 14 | [test_case.md](../backend/tests/test_case.md#ranking-orchestrator) |
| [unit/test_relavance_matrics/mrr@10.py](../backend/tests/unit/test_relavance_matrics/mrr@10.py) | helper |  |  |
| [unit/test_relavance_matrics/nDCG@10.py](../backend/tests/unit/test_relavance_matrics/nDCG@10.py) | helper |  |  |
| [unit/test_relavance_matrics/precision@10.py](../backend/tests/unit/test_relavance_matrics/precision@10.py) | helper |  |  |
| [unit/test_relavance_matrics/recall@100.py](../backend/tests/unit/test_relavance_matrics/recall@100.py) | helper |  |  |
| [unit/test_relavance_matrics/relavance_runner.py](../backend/tests/unit/test_relavance_matrics/relavance_runner.py) | helper |  |  |
| [unit/test_relevance_metrics_base.py](../backend/tests/unit/test_relevance_metrics_base.py) | tests | 7 |  |
| [unit/test_search_pipeline.py](../backend/tests/unit/test_search_pipeline.py) | tests | 10 | [test_case.md](../backend/tests/test_case.md#search-service-pipeline) |
| [unit/test_search_telemetry.py](../backend/tests/unit/test_search_telemetry.py) | tests | 8 |  |
| [unit/test_snippet_bounds.py](../backend/tests/unit/test_snippet_bounds.py) | tests | 3 | [test_case.md](../backend/tests/test_case.md#snippets) |
| [unit/test_snippets.py](../backend/tests/unit/test_snippets.py) | tests | 57 | [test_case.md](../backend/tests/test_case.md#snippets) |

### Indexer

| File | Kind | Cases | Write-up |
|---|---|---:|---|
| [conftest.py](../crawler/tests/indexer/conftest.py) | fixtures |  | [test_case.md](../crawler/tests/test_case.md#conftestpy) |
| [test_analyzer.py](../crawler/tests/indexer/test_analyzer.py) | tests | 11 | [test_case.md](../crawler/tests/test_case.md#test_analyzerpy) |
| [test_builder.py](../crawler/tests/indexer/test_builder.py) | tests | 13 | [test_case.md](../crawler/tests/test_case.md#test_builderpy) |
| [test_concurrent_writers.py](../crawler/tests/indexer/test_concurrent_writers.py) | tests | 5 |  |
| [test_indexer.py](../crawler/tests/indexer/test_indexer.py) | tests | 2 | [test_case.md](../crawler/tests/test_case.md#test_indexerpy) |
| [test_pipeline.py](../crawler/tests/indexer/test_pipeline.py) | tests | 1 | [test_case.md](../crawler/tests/test_case.md#test_pipelinepy) |
| [test_repository.py](../crawler/tests/indexer/test_repository.py) | tests | 8 | [test_case.md](../crawler/tests/test_case.md#test_repositorypy) |
| [test_selector.py](../crawler/tests/indexer/test_selector.py) | tests | 10 | [test_case.md](../crawler/tests/test_case.md#test_selectorpy) |
| [test_service_writer.py](../crawler/tests/indexer/test_service_writer.py) | tests | 9 | [test_case.md](../crawler/tests/test_case.md#test_service_writerpy) |
| [test_vector.py](../crawler/tests/indexer/test_vector.py) | tests | 29 | [test_case.md](../crawler/tests/test_case.md#test_vectorpy) |
| [test_vocabulary.py](../crawler/tests/indexer/test_vocabulary.py) | tests | 4 | [test_case.md](../crawler/tests/test_case.md#test_vocabularypy) |
| [test_vocabulary_outbox.py](../crawler/tests/indexer/test_vocabulary_outbox.py) | tests | 6 |  |
| [test_vocabulary_rebuild_cli.py](../crawler/tests/indexer/test_vocabulary_rebuild_cli.py) | tests | 6 | [test_case.md](../crawler/tests/test_case.md#test_vocabulary_rebuild_clipy) |
| [test_worker_recovery.py](../crawler/tests/indexer/test_worker_recovery.py) | tests | 4 |  |

### Crawler

| File | Kind | Cases | Write-up |
|---|---|---:|---|
| [README.md](../crawler/tests/README.md) | write-up |  |  |
| [benchmarks/bench_claim.py](../crawler/tests/benchmarks/bench_claim.py) | helper |  | [test_case.md](../crawler/tests/test_case.md#claim-benchmark) |
| [benchmarks/bench_indexer.py](../crawler/tests/benchmarks/bench_indexer.py) | helper |  |  |
| [benchmarks/bench_search.py](../crawler/tests/benchmarks/bench_search.py) | helper |  |  |
| [benchmarks/fake_web_load.py](../crawler/tests/benchmarks/fake_web_load.py) | helper |  |  |
| [crawler/fetcher/conftest.py](../crawler/tests/crawler/fetcher/conftest.py) | fixtures |  | [test_case.md](../crawler/tests/test_case.md#conftestpy) |
| [crawler/fetcher/test_fetcher.py](../crawler/tests/crawler/fetcher/test_fetcher.py) | tests | 33 | [test_case.md](../crawler/tests/test_case.md#test_fetcherpy) |
| [crawler/frontier/test_enqueue_target.py](../crawler/tests/crawler/frontier/test_enqueue_target.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_enqueue_targetpy) |
| [crawler/frontier/test_scope.py](../crawler/tests/crawler/frontier/test_scope.py) | tests | 5 | [test_case.md](../crawler/tests/test_case.md#test_scopepy) |
| [crawler/frontier/test_urls.py](../crawler/tests/crawler/frontier/test_urls.py) | tests | 3 | [test_case.md](../crawler/tests/test_case.md#test_urlspy) |
| [crawler/ingestion/test_feeds.py](../crawler/tests/crawler/ingestion/test_feeds.py) | tests | 5 | [test_case.md](../crawler/tests/test_case.md#test_feedspy) |
| [crawler/ingestion/test_ingestion_jobs.py](../crawler/tests/crawler/ingestion/test_ingestion_jobs.py) | tests | 7 | [test_case.md](../crawler/tests/test_case.md#test_ingestion_jobspy) |
| [crawler/ingestion/test_json_api.py](../crawler/tests/crawler/ingestion/test_json_api.py) | tests | 11 | [test_case.md](../crawler/tests/test_case.md#test_json_apipy) |
| [crawler/ingestion/test_sitemap.py](../crawler/tests/crawler/ingestion/test_sitemap.py) | tests | 11 | [test_case.md](../crawler/tests/test_case.md#test_sitemappy) |
| [crawler/ingestion/test_sitemap_discovery.py](../crawler/tests/crawler/ingestion/test_sitemap_discovery.py) | tests | 5 | [test_case.md](../crawler/tests/test_case.md#test_sitemap_discoverypy) |
| [crawler/parser/test_html_parser.py](../crawler/tests/crawler/parser/test_html_parser.py) | tests | 28 | [test_case.md](../crawler/tests/test_case.md#test_html_parserpy) |
| [crawler/parser/test_robots_metadata.py](../crawler/tests/crawler/parser/test_robots_metadata.py) | tests | 1 | [test_case.md](../crawler/tests/test_case.md#test_robots_metadatapy) |
| [crawler/policy_and_politeness/test_dns_policy.py](../crawler/tests/crawler/policy_and_politeness/test_dns_policy.py) | tests | 19 | [test_case.md](../crawler/tests/test_case.md#test_dns_policypy) |
| [crawler/policy_and_politeness/test_host_policy.py](../crawler/tests/crawler/policy_and_politeness/test_host_policy.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_host_policypy) |
| [crawler/policy_and_politeness/test_policy_coordinator.py](../crawler/tests/crawler/policy_and_politeness/test_policy_coordinator.py) | tests | 23 | [test_case.md](../crawler/tests/test_case.md#test_policy_coordinatorpy) |
| [crawler/policy_and_politeness/test_politeness_policy.py](../crawler/tests/crawler/policy_and_politeness/test_politeness_policy.py) | tests | 40 | [test_case.md](../crawler/tests/test_case.md#test_politeness_policypy) |
| [crawler/policy_and_politeness/test_redirect_policy.py](../crawler/tests/crawler/policy_and_politeness/test_redirect_policy.py) | tests | 23 | [test_case.md](../crawler/tests/test_case.md#test_redirect_policypy) |
| [crawler/policy_and_politeness/test_robots_policy.py](../crawler/tests/crawler/policy_and_politeness/test_robots_policy.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_robots_policypy) |
| [crawler/policy_and_politeness/test_robots_rules.py](../crawler/tests/crawler/policy_and_politeness/test_robots_rules.py) | tests | 6 | [test_case.md](../crawler/tests/test_case.md#test_robots_rulespy) |
| [crawler/policy_and_politeness/test_shared_politeness.py](../crawler/tests/crawler/policy_and_politeness/test_shared_politeness.py) | tests | 6 |  |
| [crawler/processing/test_fingerprint.py](../crawler/tests/crawler/processing/test_fingerprint.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_fingerprintpy) |
| [crawler/processing/test_processing.py](../crawler/tests/crawler/processing/test_processing.py) | tests | 58 | [test_case.md](../crawler/tests/test_case.md#test_processingpy) |
| [crawler/scheduler/test_complete_target.py](../crawler/tests/crawler/scheduler/test_complete_target.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_complete_targetpy) |
| [crawler/scheduler/test_concurrent_claims.py](../crawler/tests/crawler/scheduler/test_concurrent_claims.py) | tests | 3 | [test_case.md](../crawler/tests/test_case.md#test_concurrent_claimspy) |
| [crawler/scheduler/test_fail_target.py](../crawler/tests/crawler/scheduler/test_fail_target.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_fail_targetpy) |
| [crawler/scheduler/test_repository.py](../crawler/tests/crawler/scheduler/test_repository.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_repositorypy) |
| [crawler/worker/test_availability.py](../crawler/tests/crawler/worker/test_availability.py) | tests | 2 | [test_case.md](../crawler/tests/test_case.md#test_availabilitypy) |
| [crawler/worker/test_database_faults.py](../crawler/tests/crawler/worker/test_database_faults.py) | tests | 2 |  |
| [crawler/worker/test_deadlock_retry.py](../crawler/tests/crawler/worker/test_deadlock_retry.py) | tests | 3 | [test_case.md](../crawler/tests/test_case.md#test_deadlock_retrypy) |
| [crawler/worker/test_live_pipeline.py](../crawler/tests/crawler/worker/test_live_pipeline.py) | tests | 0 | [test_case.md](../crawler/tests/test_case.md#test_live_pipelinepy) |
| [crawler/worker/test_monitoring.py](../crawler/tests/crawler/worker/test_monitoring.py) | tests | 4 | [test_case.md](../crawler/tests/test_case.md#test_monitoringpy) |
| [crawler/worker/test_postgres_pipeline.py](../crawler/tests/crawler/worker/test_postgres_pipeline.py) | tests | 9 | [test_case.md](../crawler/tests/test_case.md#test_postgres_pipelinepy) |
| [crawler/worker/test_recovery.py](../crawler/tests/crawler/worker/test_recovery.py) | tests | 5 | [test_case.md](../crawler/tests/test_case.md#test_recoverypy) |
| [crawler/worker/test_runner_continuous.py](../crawler/tests/crawler/worker/test_runner_continuous.py) | tests | 5 |  |
| [crawler/writer/test_database_writer.py](../crawler/tests/crawler/writer/test_database_writer.py) | tests | 7 | [test_case.md](../crawler/tests/test_case.md#test_database_writerpy) |
| [test_case.md](../crawler/tests/test_case.md) | write-up |  |  |

### Frontend (Next.js, admin)

- `npm run test:integration` runs `node tests/integration.mjs`
- `npm run test:admin` runs `node tests/admin-integration.mjs`
- `npm run test:admin:unit` runs `node --experimental-strip-types tests/admin-unit.mjs && node --experimental-strip-types tests/crawler-monitor-unit.mjs && node --experimental-strip-types tests/indexer-report-unit.mjs`
- `npm run test:admin:routes` runs `node --experimental-strip-types tests/admin-routes.mjs`
- `npm run test:search:unit` runs `node --experimental-strip-types tests/search-unit.mjs && node --experimental-strip-types tests/knowledge-unit.mjs`
- `npm run test:overview:unit` runs `node --experimental-strip-types tests/overview-unit.mjs`
- `npm run test:overview:routes` runs `node tests/overview-routes.mjs`

| File | Kind | Cases | Write-up |
|---|---|---:|---|
| [README.md](../frontend/tests/README.md) | write-up |  |  |
| [admin-integration.mjs](../frontend/tests/admin-integration.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#admin-integrationmjs) |
| [admin-routes.mjs](../frontend/tests/admin-routes.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#admin-routesmjs) |
| [admin-unit.mjs](../frontend/tests/admin-unit.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#admin-unitmjs) |
| [crawler-monitor-unit.mjs](../frontend/tests/crawler-monitor-unit.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#crawler-monitor-unitmjs) |
| [fixtures/crawler-monitor.mjs](../frontend/tests/fixtures/crawler-monitor.mjs) | fixture data |  | [test_case.md](../frontend/tests/test_case.md#fixtures) |
| [fixtures/crawler-report.mjs](../frontend/tests/fixtures/crawler-report.mjs) | fixture data |  | [test_case.md](../frontend/tests/test_case.md#fixtures) |
| [fixtures/system-report.mjs](../frontend/tests/fixtures/system-report.mjs) | fixture data |  |  |
| [indexer-report-unit.mjs](../frontend/tests/indexer-report-unit.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#indexer-report-unitmjs) |
| [integration.mjs](../frontend/tests/integration.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#integrationmjs) |
| [knowledge-unit.mjs](../frontend/tests/knowledge-unit.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#knowledge-unitmjs) |
| [overview-routes.mjs](../frontend/tests/overview-routes.mjs) | tests | script |  |
| [overview-unit.mjs](../frontend/tests/overview-unit.mjs) | tests | script |  |
| [preview-crawler.mjs](../frontend/tests/preview-crawler.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#preview-crawlermjs) |
| [preview-overview.mjs](../frontend/tests/preview-overview.mjs) | tests | script |  |
| [search-unit.mjs](../frontend/tests/search-unit.mjs) | tests | script | [test_case.md](../frontend/tests/test_case.md#search-unitmjs) |
| [test_case.md](../frontend/tests/test_case.md) | write-up |  |  |
<!-- test-index:end -->
