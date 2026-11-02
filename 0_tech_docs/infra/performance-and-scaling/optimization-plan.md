# Optimization targets and decision gates

Status: **proposed**, reviewed at `facd333` on 2026-11-02. These are ordered investigation targets, not completed work or agreed production SLOs. Establish a representative baseline before choosing numeric latency/throughput budgets.

## Correctness and integration first

| Order | Target | Why it precedes optimization | Completion evidence |
| --- | --- | --- | --- |
| 1 | Repair vocabulary additions and missing deletion mutex | Wrong counts invalidate fuzzy frequency evidence and concurrency assumptions | Multi-term lifecycle plus concurrent real-PostgreSQL tests and exact recount; INC-0007 |
| 2 | Repair fuzzy imports and missing candidate implementation | Component cannot import; more infrastructure cannot fix it | Import smoke test, pg_trgm fixtures, protected-token correction tests; INC-0008 |
| 3 | Adapt and connect analyzer/planner/retrieval/merge contracts | Current FTS is dual-channel and output types differ | Route tests for all/text/code, no duplicate inflation, reconciled query bounds |
| 4 | Define ranking query lexemes and corpus ownership | Raw query normalization is not positive-lexeme extraction; stale N can be inconsistent | English/simple, phrase/negative/stopword/empty fixtures; documented snapshot policy |
| 5 | Implement scorer and orchestrator against known inputs | Empty files are not a completed BM25 engine | Numeric score tests, zero/missing-data behavior, deterministic ranking and EXP-0004 |
| 6 | Integrate top-result snippets and the public contract | Component spans use Python offsets; frontend uses UTF-16 indices | Emoji/code/plain-text tests, max_chars checks and end-to-end contract validation |

## Database and index work

| Target | Hypothesis / proposed change | Measure | Gate and accepted cost |
| --- | --- | --- | --- |
| BM25 TF/DL | Store exact per-document per-channel statistics during indexing, potentially per-field if field-aware ranking is chosen | Query CPU/rows/buffers, persisted bytes, index throughput and relevance | Only after term/channel semantics are stable; maintain insert/update/delete/rebuild atomically and account for write amplification |
| Channel DF | Maintain channel-specific document frequencies instead of online counts | Per-term count cost and update contention | Do not reuse filtered combined search_terms as exact DF; require a reconciliation path |
| Corpus snapshots | Maintain N/total length/avgdl outside query serving with an explicit generation/freshness policy | Refresh duration, stale-snapshot rate, invalid DF>N cases | Define stale/read-consistency behavior first; do not silently clamp inconsistent stats |
| Candidate budget | Tune bounded candidate counts or category-aware retrieval | Recall@candidate_limit, underfilled categories and p95 latency | Preserve judged recall; do not increase every query limit blindly |
| Retrieval plans | Inspect GIN matching, rank sorts and availability/category joins | EXPLAIN (ANALYZE, BUFFERS), rows filtered, sort memory | Use representative common/rare terms; document every index's write/storage cost |
| Vocabulary mutex | Reduce transaction scope or later prototype finer locking | Advisory-lock wait, committed documents/s, drift after full recount | Fix INC-0007 first; any count drift rejects the optimization (EXP-0006) |
| Indexer repeated failures | Add bounded durable retry/backoff or quarantine | Repeated failed document IDs and useful work per poll | Specify revival/retry/version behavior; keep freshness repair possible |
| Reindex/version rollout | Avoid expensive repeated stale scans and clarify mixed-version reads | Index lag, selector plans, new/old version counts | Maintain document revision checks and version compatibility; no undocumented destructive rebuild |

## Serving and UI work

| Target | Proposed direction | Evidence required before adoption |
| --- | --- | --- |
| Request orchestration | Hydrate and generate snippets only for final top results; batch SQL; keep shared AsyncSession sequential | Stage latency profile and correct ordering/filter contracts |
| Snippet input cost | Bound or preselect text passed into regex scanning | Long-document benchmark and later-passage relevance fixtures; candidate caps alone do not bound scanning |
| Search caching | Cache selected public responses with query/mode/filter/page and index/statistics generation in the key | Hit rate, stale-result bounds, invalidation behavior and a policy for failures; admin data bypasses public cache |
| Nginx | Evaluate proxy/TLS/timeouts/rate limits and possibly explicit public cache rules | A deployed configuration and observed behavior; it is not a SQL optimizer or query planner |
| Pagination | Define stable ordering, candidate limits and cursor/offset semantics | Duplicate/missing-result checks under index updates and realistic deep-page query cost |
| Frontend effects | Profile WebGL, animation and pasted-code preview; consider lazy loading | Mobile/low-end interaction and bundle profiles plus reduced-motion/non-WebGL checks |
| HTTP connection reuse | Pool only where approved URL/IP/Host/TLS policy remains enforced per request | Handshake cost profile and security regression suite; never trade away pinning for throughput |

## Crawl and operations work

| Target | Trigger | Measurement / prerequisite |
| --- | --- | --- |
| Shared host limiter | Before a second crawler process uses overlapping hosts | Aggregate host starts/in-flight limits across processes, Retry-After and failure recovery |
| Scheduler changes | Sustained due backlog or claim latency in a representative workload | Reproduce EXP-0001 and extend workload; keep no duplicate live claims, source fairness and lease fencing |
| Frontier budget contention | Source insertion lock waits dominate | Enqueue duration/inserted rows and concurrent budget correctness |
| More formats or headless rendering | A required source cannot be acquired by static HTTP/adapters | Source-specific extraction quality, resource use and safety design |
| Raw-page archival | Need replay without upstream refetch | Retention, versioning, privacy, storage cost and parser reproducibility design |
| Telemetry retention | Event/log growth or reporting scans compete with useful work | Relation sizes, query plans, retention window and incident-debugging needs |
| Strong report snapshots | Automated action depends on cross-table count agreement | Snapshot isolation or one-statement design with measured cost |
| CI/containers | Before automated shared deployment | Disposable PostgreSQL clean-install/upgrade runs and frontend checks, ADR-0039 |
| Readiness/operations | Before production traffic | Health vs DB readiness, backups/restore, shutdown/recovery, migration and credential procedures |
| External search engine / broker | Measured limits persist after local query/index work | Same-corpus relevance/latency/cost comparison and complete delivery/rebuild semantics |

## Evidence rules

The historical scheduler benchmark in [EXP-0001](../../crawler/scheduler-and-leases/EXP-0001-claim-path-concurrency-benchmark.md) is the only retained measured throughput/latency experiment in this record set. It used synthetic targets on one machine and is not a production capacity claim.

[EXP-0003](../../backend/bm25-statistics/EXP-0003-ranking-statistics-round-trip-audit.md) is static SQL-call accounting, not a performance benchmark. [EXP-0004](../../backend/ranking/EXP-0004-lexical-relevance-evaluation.md), [EXP-0005](EXP-0005-search-and-ingestion-capacity-baseline.md) and [EXP-0006](../../indexer/vocubulary/EXP-0006-vocabulary-lock-contention.md) are unrun protocols. No exact QPS or latency target is presented as achieved.

For each experiment, retain commit, configuration, data/hash, hardware, sample count, cold/warm state, raw output, errors and correctness results. Change one dimension where possible, report median/tail metrics and reject faster variants that break invariants. Cache hits, uncached SQL, request submission rate and useful completed work must be reported separately.
