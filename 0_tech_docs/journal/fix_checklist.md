# Fix checklist

Audited 2026-11-04; engineering checklist completed on `fix/checklist` on 2026-11-09. Final verification: 12 suites, 1,328 tests/checks, zero failures or skips on both Windows/PostgreSQL 18.3 and a fresh Ubuntu 26.04 checkout/PostgreSQL 18.6. Both real Next.js-to-FastAPI stack runs passed, including twelve repeated search/suggestion disconnects against locked PostgreSQL tables. Real browser automation and production deployment were not run.

Evidence and reproduction: [completion journal](checklist-completion-2026-11-09.md), [machine-readable verification](../../backend/reports/checklist/verification.json). Optional counters, DNS/HTTP caches, fillfactor changes and `de_core` extraction were evaluated and deferred with explicit prerequisites; checked evaluation items do not claim these features shipped. The final three sections are intentionally unchanged.

Ticked items with no automated test behind them (keep ticked, but know the evidence is manual):
- Key rotation, old-key 401/403 and deployment checks: one-off local checks recorded in INC-0006.
- "Keep crawling to one process": a convention, nothing in code enforces it.
- "Verify correct DF (299...)": a one-off live measurement. The mechanism is tested by test_df_matches_exact_lexemes_not_double_stems.
- Secret scanning: the workflow exists, a successful run on GitHub was not checked from here.

## P0 · Security and immediate safeguards
- [x] Rotate CRAWLER_REPORT_API_KEY in every applicable environment.
- [x] Verify that the previously exposed key returns 401/403.
- [x] Check whether the key was deployed anywhere beyond local development.
- [x] Ensure backend and frontend use the new key without committing it.
- [x] Add automated secret scanning to prevent recurrence.
- [x] Keep crawling to one process until politeness is enforced across processes. (done: politeness is now enforced across processes, see ADR-0042)

## P1 · BM25 and ranking correctness
- [x] Fix double-stemming of indexed lexemes in statistics.py.
- [x] Add regression: universe → univers, not univ.
- [x] Verify correct DF (299 in the audited corpus versus erroneous 4).
- [x] Verify TF, DF, DL, avgDL, N and IDF calculations.
- [x] Verify scoring behavior for missing terms, short documents and empty vectors.
- [x] Check TEXT, CODE and ALL channel statistics independently.
- [x] Test scoring for multi-term and identifier-heavy developer queries.



## P1 · Corpus statistics
- [x] Replace indefinite startup-only corpus statistics snapshots. (background refresh every 10 minutes, keeps the last good snapshot on failure)
- [x] Establish consistency rules for N, avgDL and live DF. (N is raised to fit live DF: _consistent_corpus, unit tested)
- [x] Reproduce and fix the df > N failure after indexing new documents. (test_live_counts_above_an_old_snapshot_raise_n_instead_of_failing)
- [x] Ensure stale internal statistics never return a misleading user 422. (stale counts no longer raise)
- [x] Measure and optimize startup corpus-statistics loading. (sampled avgDL, see EXP-0008)
- [x] Add integration tests for searching while the index grows or shrinks.

## P1 · Search relevance
- [x] Compare custom BM25 ordering against PostgreSQL's native ranking. (EXP-0014: frozen 25-query real-corpus comparison, 328 agent grades with explicit assessor limitations; reports at five and ten results)
- [x] create a pre golden ranking test
- [x] Implement Recall@100 for candidate retrieval.
- [x] Implement Precision@10 for result relevance.
- [x] Implement MRR@10 for first relevant result.
- [x] Implement nDCG@10 for ranking quality.
- [x] Compare all four metrics against PostgreSQL's native ranking.
- [x] Record evaluation results in EXP-0004.
- [x] Create documented golden ranking tests with expected score/order.

## P1 · Retrieval, filtering and API integration
- [x] Pass source, category, mode, page and page size through the UI, proxy and backend. (category chips, mode controls, bounded page/limit and language preference flow through UI, shared URLs, proxy and API; ADR-0053)
- [x] Apply eligible source/category filters before per-channel candidate limits. (stored search_index.category)
- [x] Fix backend global top-100-per-channel cutoff for restricted searches. (filters run inside retrieval)
- [x] Fix the frontend's client-only filtering of the initial 20 results. (filter chips search the server)
- [x] Reproduce fastapi event results: 13 existing events, zero surviving candidates.
- [x] Implement deterministic pagination and stable tie-breaking. (tests: test_pagination, test_equal_bm25_scores_break_ties_by_document_id)
- [x] Wire TEXT, CODE and ALL mode selection end to end. (backend, proxy and UI wired; real-stack code-mode and frontend integration checks pass)
- [x] Define combined Discussions category and its source/type mapping. (stackoverflow + reddit in backend.search.categories, integration tested)
- [x] Connect spelling/fuzzy suggestions through the API and UI. (UI explicit suggestion display, validated proxy and real-stack integration pass)
- [x] Validate invalid filters, empty queries, deep paging and no-result responses. (tests: api/test_search (422 cases), test_invalid_pagination_rejected_without_db_access, test_no_match_returns_empty)
- [x] Add API request limits, query-size limits, deadlines and cancellation handling. (ADR-0046)
- [x] Implement public API rate limiting with HTTP 429. (per client, per process; Next.js forwards the client address, compose sets FORWARDED_ALLOW_IPS)
- [x] Implement total search deadline using asyncio.timeout(). (4 s, /search and /search/suggest)
- [x] Map database timeout errors to HTTP 504. (statement_timeout and connection pool timeout; tested against real PostgreSQL)
- [x] Propagate client cancellation through Next.js. (request.signal on the upstream call)
- [x] Handle backend client disconnects safely. (cancels the query in PostgreSQL, frees the slot only after unwinding)
- [x] Align frontend/backend query-length constraints. (256 normalized, 1024 raw, counted the same way; test_frontend_query_limits_match_the_backend)
- [x] Add overload, timeout and cancellation tests. (test_search_limits, test_search_deadlines, frontend integration.mjs)
- [x] Run fresh frontend-to-backend integration tests. (backend/scripts/e2e_search_stack.py: real Next.js and FastAPI on a newly migrated database, passed 2026-11-08)

## P1 · Crawler discovery and correctness
- [x] Fix the 1,000-URL sitemap cap with resumable continuation. (all entries queue in short idempotent transactions)
- [x] Add 1,001+ sitemap URL regression coverage including repeated runs. (test_sitemap_past_link_limit_queues_every_url_and_rerun_adds_nothing)
- [x] Preserve bounded processing and crawler restart safety. (capped at 50,000 entries per sitemap, retry is idempotent)
- [x] Review nested sitemap indexes and continuation behavior. (nested child scoping/depth, deduplication, and partial-commit retry/replay pass against a freshly migrated PostgreSQL database; test_postgres_pipeline.py)
- [x] Shorten DB transactions so no connection stays held across HTTP fetching. (ShortTransactions in jobs.py)
- [x] Read/write robots cache with short sessions and consider in-process TTL caching. (short sessions done, TTL cache not needed yet)
- [x] Move index/vocabulary mutation out of crawler finalize and assign it to indexer ownership. (crawler only marks documents unavailable on 404, 410 and noindex; the indexer removes the index rows)
- [x] Remove lease recovery work from every claim; design one periodic reaper. (reap_forever, one process at a time through an advisory lock)
- [x] Drive orphan recovery from unfinished attempts with appropriate indexing. (ix_crawl_attempt_unfinished and ix_crawl_target_lease)
- [x] Make startup seeding/discovery single-owner or advisory-lock guarded. (sync_sources_once)
- [x] Test lease expiry, fencing, retries, backoff and recovery after crashes. (PostgreSQL concurrency, recovery, fencing, deadlock and pipeline regressions; test_legacy_contracts now collects all three rollback-only scheduler scripts in pytest/CI with an explicit test database)
- [x] Preserve SSRF pinning, robots compliance and Retry-After behavior through refactors.

## P2 · Indexer, vocabulary and data integrity
- [x] Fix after_document_id cursor handling in removal pagination. (selector now applies the cursor)
- [x] Add removal regression for after_document_id=999. (test_removal_cursor_is_part_of_the_query)
- [x] Introduce bounded failure backoff so failed removals cannot monopolize the first page. (the working cursor moves past failed removals)
- [x] Coordinate vocabulary mutex/locking across upserts, removals and rebuilds. (no shared lock for writers now: outbox plus one drainer, test_vocabulary_outbox)
- [x] Recheck 404/410, noindex and document tombstoning behavior. (ADR-0050: a missing or noindex feed no longer marks its articles, a feed cannot revive a removed page, test_postgres_pipeline.py)
- [x] Verify search_index and search_terms remain transactionally consistent. (change row commits with the index write; exact recount in bench_indexer shows 0 wrong)
- [x] Stop vocabulary drift from aborting crawl finalization (writers only append to the outbox)
- [x] Validate vocabulary DF never becomes negative and matches indexed documents. (exact recount 0 wrong at 1 and 4 processes)
- [x] Ensure feed/API summaries cannot silently overwrite fuller canonical page content. (ADR-0050, enforced in the upsert, logged as kept_existing)
- [x] Preserve acquisition provenance, original source ownership and content quality. (ADR-0052, INC-0037: original source retained, atomic per-target provenance, selected producer recorded, thin competing pages rejected; 29 PostgreSQL writer/pipeline tests pass)
- [x] Test hash-unchanged indexing, updates, removals and rebuild consistency. (test_index_lifecycle.py on real Postgres)
- [x] Review indexer batching and mutex serialization before adding more workers. (EXP-0006 and EXP-0008: 60 docs/s to 581 docs/s)

## P2 · Database, migrations and runtime reliability
- [x] Test migration 28efc23fadfc against a populated pre-migration database. (test_migrations.py with rows at this revision; the earlier run on the real copy did not exercise it, INC-0034)
- [x] Repair the non-null code_vector upgrade/backfill path where required. (INC-0034, ADR-0047)
- [x] Test Alembic upgrade head on both empty and populated disposable Postgres 16. (empty and populated on 16 and 18; populated is the real 42k-document copy, down to e94b530df145 and back to head)
- [x] Review query plans and GIN/B-tree index use for retrieval and frontier claiming. (EXP-0010 on a real-data copy, on Postgres 18; added ix_document_last_crawl_target_id)
- [x] Review DB session and transaction boundaries across all services. (database-schema overview)
- [x] Correct unused unbound get_db() or remove it. (now uses SessionFactory)
- [x] Configure explicit engine pool sizes, timeouts and overflow policies. (db_pool_* settings)
- [x] Test DB connection loss, transaction rollback and worker recovery. (EXP-0011 real server stop, INC-0035, test_database_faults.py)
- [x] Design and verify database backup restoration before production. (deploy/backup.sh and restore-test.sh ran unchanged on a Postgres 16 copy of the real 42k-document data, 244 MB dump, all row counts matched)
- [x] Review concurrency-sensitive updates under simultaneous crawler/indexer writers. (EXP-0011, test_concurrent_writers.py)

## P2 · Test quality, dependency security and CI
- [x] Fix backend's 2 failed tests and investigate 16 skips. (all pass, 0 skipped)
- [x] Fix crawler/indexer's 3 failed tests and investigate 19 skips. (all pass, 0 skipped)
- [x] Repair fuzzy test collection failure from the removed import. (suite removed with get_fuzzy_search)
- [x] Repair stale package-boundary test imports and mocks. (backend.admin_services)
- [x] Preserve passing DNS safety tests (73/73). (73 DNS safety cases remain covered; orchestrated crawler suite uses asyncio auto mode and passes on Windows and Linux)
- [x] Add PostgreSQL integration tests for each reproduced defect. (writer ownership/provenance/quality and rollback, category repair dry-run/idempotence, language paging, telemetry atomicity/failures, scheduler contracts and real-stack cancellation; both migrated test databases pass)
- [x] Create GitHub Actions with Postgres 16, Alembic and backend/crawler pytest. (.github/workflows/ci.yml, has not run on GitHub yet)
- [x] Add frontend lint, TypeScript typecheck and production build to CI. (ci.yml)
- [x] Upgrade Next.js to a patched version and validate relevant advisories. (16.4.5, npm audit reports 0)
- [x] Run dependency and secret scans in CI. (gitleaks, npm audit and pip-audit)
- [x] Verify the complete fresh-clone setup on a clean machine/container. (fresh Linux Git clone, independent Poetry installs, npm ci, empty PostgreSQL migration, all 12 suites/1,328 checks and real-stack integration pass; INC-0039, INC-0040)

## P2 · Search relevance and UX quality
- [x] Create a 20–30-query judged relevance dataset. (25 real-corpus queries, 328 editorial agent grades, frozen rankings and independent reference checks; assessor/blinding limits explicit, EXP-0014)
- [x] Include code identifiers, error messages, phrases, typos and multi-term queries. (checklist-25 manifest; typo retrieval is an actual scored miss)
- [x] Include source-restricted, version-specific and category-specific queries. (Docs/GitHub source restrictions and Python 3.12/3.14 queries; coverage limitations recorded)
- [x] Record relevance of top-5/top-10 results and compare changes. (offline reproducible BM25/PostgreSQL P/MRR/nDCG reports at both cutoffs; unchanged weights, EXP-0014)
- [x] Investigate Russian/Portuguese pages outranking relevant English pages. (historical diagnostics reviewed; current 100k FastAPI Depends query does not reproduce the old order, recorded in ADR-0053 and raw language-preference report)
- [x] Define language preference without permanently hiding other languages. (ADR-0053: explicit stable preference preserves candidate identities and BM25 scores; real PostgreSQL regression)
- [x] Group or distinguish versions, translations and canonical duplicates. (recognized locale/version URL families and exact content hashes labeled as related variants, no URLs hidden; bounded candidate scope)
- [x] Review 832 FastAPI pages classified as other and their UI article mapping. (INC-0038: current snapshot has 52 other; 116 derived-category repairs identified, exact-host classification and idempotent repair implemented)
- [x] Show trustworthy source, version, language and freshness metadata. (declared/path language, known URL versions, last observation date; no inferred publication dates)
- [x] Improve code excerpts and highlight relevance in search snippets. (bounded query-relevant code selection; preserved code layout and escaped identifier/Unicode highlighting)
- [x] Evaluate ranking against a stored benchmark before adjusting weights. (EXP-0014: mixed results, no weight change adopted; human-reviewed holdout still required before tuning)

## P2 · Measured performance optimization
- [x] Create repeatable search benchmarks under controlled ingestion. (bench_search.py; no ingestion running yet)
- [x] Capture p50/p95/p99 latency, SQL counts and query plans. (EXP-0013, raw per-sample JSON and ANALYZE/BUFFERS plans; five samples, tail-resolution limitation recorded)
- [x] Investigate the audited 75 ms, 515 ms and 2.53 s search variation. (EXP-0013 separates query selectivity, DF-cache misses, vector expansion, and hydration; cold common-term cost remains explicit)
- [x] Profile live term-document-frequency counting. (common term sequential scan 998.509 ms; rare code-term GIN 0.766 ms, EXP-0013)
- [x] Profile TSVECTOR expansion and candidate metadata loading. (per-stage SQL timing, EXP-0013)
- [x] Fetch complete code blocks/large metadata only after final page selection. (candidate query projects tags only; page query loads code blocks; 35 search/snippet regressions pass)
- [x] Review indexes for high-frequency terms and candidate retrieval. (existing text/code GIN and category B-tree reviewed with real query plans, EXP-0013)
- [x] Measure startup time and corpus-statistics refresh costs. (1.5 s at 2M, EXP-0008)
- [x] Persist additional ranking statistics only if measurements justify maintenance cost. (evaluated and deferred: cold-read cost measured, write/backfill/reconciliation cost not justified; explicit revisit gate in EXP-0013)

## Scaling · Crawler redesign, before 30+ processes
- [x] Build a fake-web crawl-load harness, not a benchmark against public documentation sites. (tests/benchmarks/fake_web_load.py)
- [x] Record EXP-0002 baseline for stage latency, rate, DB waits and politeness violations. (recorded as EXP-0008)
- [x] Create a shared crawl_host scheduling model with next_allowed_at, in-flight and backoff state. (crawl_host; the hold doubles as the in-flight marker)
- [x] Make host request-start constraints atomic across processes. (test_shared_politeness, harness shows 0 violations)
- [x] Write ADR-0041 to update the earlier politeness architecture. (written as ADR-0042)
- [x] Replace multiple claim queries with an atomic SKIP LOCKED claim where measured beneficial. (one statement in scheduler/repository.py)
- [x] Add partial indexes matching host-aware frontier selection. (ix_crawl_target_host_due)
- [x] Replace batch-barrier execution with continuous bounded worker slots. (run_continuous, test_runner_continuous)
- [x] Evaluate LISTEN/NOTIFY to reduce idle polling. (rejected: idle claims are cheap and hosts become ready by time, not by an event)
- [x] Reduce per-crawl DB transactions and telemetry write amplification. (ADR-0055, EXP-0015: batched CPU checkpoints/atomic terminal summary; one-worker transactions/request 8.88 → 7.91, updated tuples/request 10.03 → 5.00)
- [x] Replace source-wide frontier COUNT queries with maintained counters if verified safe. (evaluated and deferred: largest-source count 10.742 ms; cross-path counter correctness not established, so preserve exact budget checks; EXP-0015)
- [x] Evaluate safe HTTP connection reuse with host/IP pinning. (retain request-scoped pinning; pooled origin/IP-set lifecycle and DNS/TLS measurements required before reuse; EXP-0015)
- [x] Evaluate safe DNS TTL caching and conditional GET / 304 reuse. (deferred: getaddrinfo lacks TTL and validator ownership/request-header lifecycle is not implemented; existing 304 handling retained, EXP-0015)
- [x] Deploy and profile crawlers in Linux before changing event-loop settings. (local Ubuntu/WSL deployment and staged real-worker fake-web runs; no public production deployment or event-loop change; EXP-0015)
- [x] Size DB pools across processes; evaluate PgBouncer and prepared-statement behavior. (2 crawlers + 2 indexers + API fit in max_connections 60 without PgBouncer)
- [x] Evaluate crawl_target fillfactor/autovacuum and crawl_event retention. (HOT/dead tuple/table stats and deployment-vs-local vacuum settings captured; keep storage settings, bounded 14-day purge already exists, zero local events eligible; EXP-0015)
- [x] Expand eligible, policy-compliant hosts and source categories. (already expanded in current registry: 380 enabled website/RSS/API sources, 316 hosts, initial scope checks pass; runtime robots/pinning/pacing still mandatory. Budgets total 598,245 pages, not proof of 2M capacity; EXP-0015)
- [x] Increase workers in stages, verifying aggregate politeness and throughput each time. (Linux 1/2/4/8 workers: 54.79/58.77/59.64/67.41 requests/s, zero gap/overlap violations and all child exits zero; short fake-web runs only, EXP-0015)

## Maintenance · Code structure and architectural debt
- [x] Break up long process_job and _finalize logic by job type and outcome. (resource outcome/parsing dispatch, target transition, missing/noindex and document storage helpers; worker regressions pass, ADR-0054)
- [x] Split the 955-line search-experience.tsx into testable UI components. (result rows, snippets, favicon, knowledge panel, suggestion display, and source icons extracted into components/search; lint and TypeScript pass)
- [x] Consolidate frontend's two API clients into a consistent typed interface. (one JSDoc-typed AxiosInstance factory; browser/server origin and credential boundaries retained, no duplicate transport defaults)
- [x] Evaluate a small shared de_core package for DB models and common runtime contracts. (ADR-0054: retain existing one-way backend schema dependency; extraction deferred until an independent consumer or measured packaging benefit exists)
- [x] Review ownership boundaries between crawler, indexer and API. (ADR-0054 ownership table; obsolete crawler-to-indexer mutation imports removed)
- [x] Remove dead imports/functions and obsolete tests and docs. (dead/duplicate imports removed from the refactored job/finalize modules; no duplicate top-level Python definitions found; superseded acquisition rules labeled)
- [x] Keep refactors in small commits separate from behavior changes. (separate result-component, HTTP-client, and worker-dispatch refactor commits)

## Tech docs · Architecture, decisions and experiments
- [ ] Verify root README and installation/runtime instructions.
- [ ] Document current architecture and complete data flow.
- [ ] Document crawler frontier, scheduler, leases, politeness, fetcher and parser.
- [ ] Document indexer selection, vector construction, transactional writes and vocabulary lifecycle.
- [ ] Document query analyzer, retrieval modes, ranking, snippets and API boundaries.
- [ ] Document database models, relationships, indexes and migrations.
- [ ] Document security model, SSRF controls, admin authentication and secret handling.
- [ ] Document frontend proxy, filter semantics and pagination contracts.
- [ ] Review ADRs for assumptions, status, supersession and implemented-versus-planned claims.
- [ ] Record confirmed bugs as incident reports with reproduction and resolution tests.
- [x] Record ranking and crawl measurements as reproducible EXP reports. (EXP-0008 for crawl, index and search speed; ranking quality is still EXP-0004)
- [ ] Update optimization-plan.md with dependencies and measured prerequisites.
- [ ] Repair five reported broken documentation links.
- [ ] Verify all diagrams, glossary entries and documentation navigation.

## Technical writing · Three engineering blogs
- [ ] Draft: Building a Polite, SSRF-Resistant Web Crawler.
- [ ] Draft: Building a PostgreSQL Full-Text Index and Transactional Vocabulary.
- [ ] Draft: Building Developer Search with Retrieval, BM25 and Snippets.
- [ ] Include accurate architecture diagrams and small concrete code excerpts.
- [ ] Explain engineering tradeoffs, failures and what measurements actually prove.
- [ ] Mark unimplemented optimizations as future work, not existing features.
- [ ] Proofread, add repository references and publish the strongest article first.

## Release gates · Required before public launch
- [x] All known P0 security findings resolved. (Next.js fixed, npm audit 0)
- [ ] All search correctness and index consistency blockers resolved.
- [ ] All automated backend, crawler and frontend release tests pass.
- [ ] Fresh Alembic install and populated-database upgrade pass.
- [ ] Secret scans and relevant dependency/security checks pass.
- [ ] Search query work is bounded by validated size, time and concurrency controls. (done in code; cold common-term queries can still hit the 3 s deadline, EXP-0008)
- [ ] Real browser end-to-end flows and error states pass.
- [ ] Production startup, search API, reverse proxy and admin auth verified.
- [ ] Backup restoration and recovery procedures validated.
- [ ] Sustained representative load testing completed without correctness failures.
- [ ] Search relevance is acceptable against a documented judged dataset.
- [ ] User-facing documentation accurately describes supported features.