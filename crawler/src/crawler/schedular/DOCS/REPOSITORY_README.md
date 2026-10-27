# Initially crawl_target status is queued.

![alt text](image.png)

- now we want to crawl the target. so we pass it to `claim_targets()`
- claim targets picks a **source** first (round robin), then the best target inside that source (priority, then BFS depth), and sets '**`state = leased`**'
   - -> we used **`FOR UPDATE SKIP LOCKED`** here. so that if worker A claims the target A no worker can touch it.
   - -> after changing to lease it gets **5min reservation** (`lease_seconds=300`). worker A now work with this for 5min time limit.

---

## How `claim_targets()` picks work: round-robin BFS

### The problem it solves (feed starving)

The old claim was one query over the whole frontier:

```sql
ORDER BY priority DESC, next_fetch_at ASC, id ASC
LIMIT n
```

So a big source with thousands of high-priority targets (a docs site with a sitemap) filled every batch, and a small source (an RSS feed with a few targets) waited until the big one ran dry. That is **starvation**: the small feed was due, but never got a turn.

Now the claim works in **two levels**:

| Level | Question | Rule | Where in `repository.py` |
| --- | --- | --- | --- |
| 1. Round robin | *Which source gets the next slot?* | the enabled source that was claimed **longest ago** | `source_query`, ordered by `Source.last_claimed_at ASC NULLS FIRST, Source.id ASC` |
| 2. BFS inside the source | *Which target of that source?* | highest priority, then **shallowest depth** | `target_query`, ordered by `priority DESC, depth ASC, next_fetch_at ASC, id ASC` |

### Level 1: round robin across sources

- `source.last_claimed_at` is the "whose turn is it" clock. It was added by the migration `5fc9efde409c_add_source_last_claimed_timestamp.py` (nullable, `NULL` = never claimed).
- a source is a candidate only if it is `is_enabled = true` **and** has at least one target with `state = 'queued'` and `next_fetch_at <= now()` (the `eligible` `EXISTS` subquery). So disabled sources and sources with nothing due are skipped and their `last_claimed_at` does not move.
- candidates are sorted `last_claimed_at ASC NULLS FIRST, id ASC`:
   - -> a source that was never claimed goes first.
   - -> after that, whoever waited the longest.
   - -> `id` only breaks ties.
- only **one** source is picked per loop step (`LIMIT 1 ... FOR UPDATE OF source SKIP LOCKED`).
- after a target is leased, that source gets `last_claimed_at = clock_timestamp()`. So it moves to the **back of the line**, and the next loop step picks someone else.

`clock_timestamp()` (not `now()`) matters here: `now()` is frozen for the whole transaction, so every source claimed in one batch would get the same time and the order would collapse. `clock_timestamp()` keeps moving, so the order inside one batch is kept.

### Level 2: BFS inside the chosen source

Inside the source, the target is picked by:

```sql
ORDER BY priority DESC, depth ASC, next_fetch_at ASC, id ASC
LIMIT 1
FOR UPDATE OF crawl_target SKIP LOCKED
```

- `priority` still wins first (seeds, sitemaps, API and reference pages stay ahead, see `priority.py` below).
- at the same priority, **lower `depth` first**. `depth` is how many links away from a seed the page is (seed = 0, set in `worker/jobs/utility.py`). Taking depth 0, then 1, then 2... is **breadth-first search** over the link graph. So we crawl the top of a docs site before going deep into one corner of it.
- then oldest `next_fetch_at`, then `id`, so the order is deterministic.

### The loop, step by step

`claim_targets(session, limit, lease_seconds, source_id)` runs this loop until it has `limit` targets:

1. pick the next source (level 1). if there is none, stop and return what we have.
2. pick that source's best target (level 2).
3. if no target came back (all of its due targets are locked by another worker right now), put the source in the `unavailable` set and go back to 1, so we don't pick it again in this call.
4. lease the target: `state = 'leased'`, `lease_until = clock_timestamp() + lease_seconds`.
5. set the source's `last_claimed_at = clock_timestamp()` (moves it to the back).
6. `flush()` and add the target to the result.

### Example

Sources A (3 due targets), B (2), C (1), none claimed before. `claim_targets(limit=6)` gives:

```
A  B  C  A  B  A
```

C has nothing left after its first turn, so it drops out and A and B keep taking turns. Inside A, a priority 80 page comes first, then the depth 0 page, then the depth 2 page. The same rotation also works across calls: with `limit=1` per call, two sources alternate instead of one source winning every time. (Both are checked in `tests/test_round_robin.py`.)

### `source_id` filter

`claim_targets(source_id=...)` (used by the runner's `--source-id` option) adds `Source.id == source_id` to level 1. The round robin then has only one candidate, so the call is just BFS inside that source.

### Where it is used

- `crawler/worker/runner.py`, `claim_batch()`: every runner loop calls `recover_expired_leases()` and then `claim_targets(limit=min(batch_size, concurrency), ...)` in one short transaction. The commit at the end of that transaction saves both the leases and the new `last_claimed_at` values.
- `crawler/worker/tests/test_postgres_pipeline.py` claims through it for the pipeline regression tests.

### Things to know

- **one source per claim transaction at a time.** the source row is locked with `FOR UPDATE SKIP LOCKED` until the claiming transaction commits. so if two workers claim at the same moment and there is only one source with due work, the second worker skips it and gets `[]` for that round. with many sources each worker just takes a different source. (this is why `test_concurrent_claims_atomic_writes_and_shared_source_budget`, two parallel claims on the same source, now gets 2 and 0 instead of 2 and 2.)
- it costs up to two small queries plus one `UPDATE source` per claimed target, instead of one query for the whole batch. fine for batch sizes like 10.
- `priority.py` (`calculate_priority()`) gives the priority numbers BFS sorts on: seed 100, sitemap 90, API 85, reference paths 80, guide paths 70, RSS 60, other pages 50. it is not wired into the frontier yet, so targets keep whatever priority they were created with.
- the docstring at the top of `repository.py` still describes the old single-query plan.

---

- suppose worker A took longer than 5min to work with target A. Now if the time expire but the job is not done postgres will keep it marked as leased always.
- **`recover_expired_leases()`** if lease_until expires it change the **`state=queued`** . this function will be called periodically

---

- **`complete_target()`**
- now if worker A complete target A within the time limit , when time expires it is sent back to **`state=queued`** with **`lease_until=None`** and a next fetch schedule

---

### `calculate_retry_delay()`

- this is a helping function to cap the failure count and delay of the process.
- it have a simple formula

```math
\text{delay} = \min\left(\text{base} \times 2^{(\text{failure\_count} - 1)},\ \text{max}\right)
```

with this formula it counts delay. **[TODO: add `full jitter` for scalability]**

**summary in one line:** for each retry delay will be increased within cap

---

### Summary

- **`claim_targets()`**- start work. round robin over sources, BFS (priority, then depth) inside a source
- **`recover_expired_leases()`** - handle if worker cant complete within deadline
- **`complete_target()`** - handle if worker completes within deadline
- **`fail_target()`** - handles if worker fails to do the work.

- if it fails multiple time **`failure_count`** counts the time. and it retries follwing **`calculate_retry_delay()`** formula. for each failure retry delay keep incresing with **cap of 1hour**.

<!-- docs-nav:start -->
## Documentation map

Every project doc, grouped by area. Generated by `scripts/update_docs_nav.py`; edit that script, not this list.

**Start here**

- [Project overview](../../../../../README.md) `README.md`
- [Technical handoff](../../../../../technical_handoff.md) `technical_handoff.md`
- [Developers Eye — Complete Engineering Checklist](../../../../DEVELOPERS_EYE_CHECKLIST.md) `crawler/DEVELOPERS_EYE_CHECKLIST.md`

**Tech docs (why)**

- [Tech docs index (decisions, incidents, experiments)](../../../../../0_tech_docs/README.md) `0_tech_docs/README.md`

**Backend (FastAPI, database)**

- [Developer's Eye backend](../../../../../backend/README.md) `backend/README.md`
- [Table notes: crawl_attempt](../../../../../backend/docs/db/crawl_attempt.md) `backend/docs/db/crawl_attempt.md`
- [Table notes: crawler_frontier](../../../../../backend/docs/db/crawler_frontier.md) `backend/docs/db/crawler_frontier.md`
- [Table notes: documents](../../../../../backend/docs/db/documents.md) `backend/docs/db/documents.md`
- [Table notes: robot](../../../../../backend/docs/db/robot.md) `backend/docs/db/robot.md`
- [Table notes: search_index](../../../../../backend/docs/db/search_index.md) `backend/docs/db/search_index.md`
- [Table notes: source](../../../../../backend/docs/db/source.md) `backend/docs/db/source.md`

**Crawler: seeds and frontier**

- [Crawler package](../../README.md) `crawler/src/crawler/README.md`
- [Sitemap Discovery and Worker Jobs](../../seed/docs/sitemap_discovery.md) `crawler/src/crawler/seed/docs/sitemap_discovery.md`
- [Seed guide](../../seed/guide.md) `crawler/src/crawler/seed/guide.md`
- [Seed list](../../seed/seed_list.md) `crawler/src/crawler/seed/seed_list.md`
- [Developers Eye — Source Registry Seed Plan](../../seed/seed_listing_plan.md) `crawler/src/crawler/seed/seed_listing_plan.md`
- [Running the frontier tests](../../frontier/tests/README.md) `crawler/src/crawler/frontier/tests/README.md`
- [Frontier test cases](../../frontier/tests/test_case.md) `crawler/src/crawler/frontier/tests/test_case.md`
- [Scheduler repository and target states](REPOSITORY_README.md) `crawler/src/crawler/schedular/DOCS/REPOSITORY_README.md` (you are here)
- [Scheduler concepts to note](new_concept_to_note.md) `crawler/src/crawler/schedular/DOCS/new_concept_to_note.md`
- [Running the scheduler tests](../tests/README.md) `crawler/src/crawler/schedular/tests/README.md`
- [Developers Eye — Scheduler Tests](../tests/test1_report.md) `crawler/src/crawler/schedular/tests/test1_report.md`
- [Schedular test cases](../tests/test_case.md) `crawler/src/crawler/schedular/tests/test_case.md`

**Crawler: fetch and policy**

- [Developer's Eye: Async Fetcher — Full Flow](../../fetcher/docs/flow.md) `crawler/src/crawler/fetcher/docs/flow.md`
- [Developer's Eye fetcher tests](../../fetcher/tests/fetcher_tests/README.md) `crawler/src/crawler/fetcher/tests/fetcher_tests/README.md`
- [Policy components overview](../../policy_and_politeness/README.md) `crawler/src/crawler/policy_and_politeness/README.md`
- [Host Policy](../../policy_and_politeness/docs/1_host_policy.md) `crawler/src/crawler/policy_and_politeness/docs/1_host_policy.md`
- [DNS/IP Policy & Safe HTTP Transport](../../policy_and_politeness/docs/2_dns_policy.md) `crawler/src/crawler/policy_and_politeness/docs/2_dns_policy.md`
- [Robots Policy. Third step of our crawler safety checks](../../policy_and_politeness/docs/3_robots_policy_docs.md) `crawler/src/crawler/policy_and_politeness/docs/3_robots_policy_docs.md`
- [Politeness Policy. Fourth step of our crawler safety checks](../../policy_and_politeness/docs/4_politeness_policy.md) `crawler/src/crawler/policy_and_politeness/docs/4_politeness_policy.md`
- [Redirect Policy: What if a website sends our crawler somewhere else?](../../policy_and_politeness/docs/5_redirect_policy.md) `crawler/src/crawler/policy_and_politeness/docs/5_redirect_policy.md`
- [Avengers assemble. Policy Coordinator. Final step of our crawler policy phase](../../policy_and_politeness/docs/6_policy_coordinator.md) `crawler/src/crawler/policy_and_politeness/docs/6_policy_coordinator.md`
- [Policy docs introduction](../../policy_and_politeness/docs/README.md) `crawler/src/crawler/policy_and_politeness/docs/README.md`
- [Running the policy and politeness tests](../../policy_and_politeness/tests/README.md) `crawler/src/crawler/policy_and_politeness/tests/README.md`
- [Policy and politeness test cases](../../policy_and_politeness/tests/test_case.md) `crawler/src/crawler/policy_and_politeness/tests/test_case.md`

**Crawler: parse, process, write**

- [JSON API Ingestion](../../parser/docs/json_api.md) `crawler/src/crawler/parser/docs/json_api.md`
- [Developer's Eye: Parser Engine](../../parser/docs/parser.md) `crawler/src/crawler/parser/docs/parser.md`
- [RSS and Atom Feed Ingestion](../../parser/docs/rss_atom.md) `crawler/src/crawler/parser/docs/rss_atom.md`
- [XML Sitemap Parser](../../parser/docs/sitemap.md) `crawler/src/crawler/parser/docs/sitemap.md`
- [Running the parser tests](../../parser/tests/README.md) `crawler/src/crawler/parser/tests/README.md`
- [Parser test cases](../../parser/tests/test_case.md) `crawler/src/crawler/parser/tests/test_case.md`
- [Classifier Model](../../processing/docs/classifier.md) `crawler/src/crawler/processing/docs/classifier.md`
- [content processing pipeline](../../processing/docs/content_processing.md) `crawler/src/crawler/processing/docs/content_processing.md`
- [Fingerprint Model](../../processing/docs/fingerprint.md) `crawler/src/crawler/processing/docs/fingerprint.md`
- [Normalizer Model](../../processing/docs/normalize.md) `crawler/src/crawler/processing/docs/normalize.md`
- [Processor Model](../../processing/docs/processor_model.md) `crawler/src/crawler/processing/docs/processor_model.md`
- [Running the processing tests](../../processing/tests/README.md) `crawler/src/crawler/processing/tests/README.md`
- [Processing test cases](../../processing/tests/test_case.md) `crawler/src/crawler/processing/tests/test_case.md`
- [Developer's Eye: Database Writer](../../writer/docs/developers_eye_writer_docs.md) `crawler/src/crawler/writer/docs/developers_eye_writer_docs.md`
- [Developer's Eye: Database Writer — Debugging & Test Report](../../writer/tests/1st_succuessful_test_report.md) `crawler/src/crawler/writer/tests/1st_succuessful_test_report.md`

**Crawler: worker and ingestion**

- [Worker Jobs — Developer's Eye](../../worker/docs/jobs_docs.md) `crawler/src/crawler/worker/docs/jobs_docs.md`
- [Runner.py — Developer's Eye Crawler Worker](../../worker/docs/runner_docs.md) `crawler/src/crawler/worker/docs/runner_docs.md`
- [Running the worker tests](../../worker/tests/README.md) `crawler/src/crawler/worker/tests/README.md`
- [Worker test cases](../../worker/tests/test_case.md) `crawler/src/crawler/worker/tests/test_case.md`
- [Testing Crawler Ingestion](../../../../tests/README.md) `crawler/tests/README.md`
- [Crawler test cases](../../../../tests/test_case.md) `crawler/tests/test_case.md`

**Crawler: fix log**

- [Test run order](../../test/order.md) `crawler/src/crawler/test/order.md`
- [Fixing PostgreSQL Deadlocks in Developer's Eye](../../test/upadte_log/update_10_20_2026_8_39_PM.md) `crawler/src/crawler/test/upadte_log/update_10_20_2026_8_39_PM.md`
- [Fixing HTTP transport error handling](../../test/update_log/01_transport_errors.md) `crawler/src/crawler/test/update_log/01_transport_errors.md`
- [Fixing fetcher policy rejections](../../test/update_log/02_policy_rejections.md) `crawler/src/crawler/test/update_log/02_policy_rejections.md`
- [Fixing pinned HTTP request validation](../../test/update_log/03_pinned_requests.md) `crawler/src/crawler/test/update_log/03_pinned_requests.md`
- [Fixing robots.txt matching](../../test/update_log/04_robots_rules.md) `crawler/src/crawler/test/update_log/04_robots_rules.md`
- [Fixing combined robots metadata](../../test/update_log/05_robots_metadata.md) `crawler/src/crawler/test/update_log/05_robots_metadata.md`
- [Connecting the deadlock retry helper](../../test/update_log/06_deadlock_retry.md) `crawler/src/crawler/test/update_log/06_deadlock_retry.md`
- [Enforcing crawl depth and source budgets](../../test/update_log/07_crawl_scope.md) `crawler/src/crawler/test/update_log/07_crawl_scope.md`
- [Fixing abandoned attempts and retry recovery](../../test/update_log/08_failure_recovery.md) `crawler/src/crawler/test/update_log/08_failure_recovery.md`
- [Fixing stored content after 404 and 410 responses](../../test/update_log/09_content_availability.md) `crawler/src/crawler/test/update_log/09_content_availability.md`
- [Fixing machine-specific and circular package dependencies](../../test/update_log/10_portable_packages.md) `crawler/src/crawler/test/update_log/10_portable_packages.md`
- [Verifying the fixes against PostgreSQL](../../test/update_log/11_postgres_regressions.md) `crawler/src/crawler/test/update_log/11_postgres_regressions.md`
- [Cleaning the frontier model whitespace](../../test/update_log/12_frontier_whitespace.md) `crawler/src/crawler/test/update_log/12_frontier_whitespace.md`
- [Resolving the remaining merge conflicts](../../test/update_log/13_merge_conflicts.md) `crawler/src/crawler/test/update_log/13_merge_conflicts.md`
- [Completing XML sitemap parsing](../../test/update_log/14_sitemap_parser.md) `crawler/src/crawler/test/update_log/14_sitemap_parser.md`
- [Wiring sitemap discovery into the worker](../../test/update_log/15_sitemap_discovery.md) `crawler/src/crawler/test/update_log/15_sitemap_discovery.md`
- [Adding RSS and Atom ingestion](../../test/update_log/16_rss_atom_ingestion.md) `crawler/src/crawler/test/update_log/16_rss_atom_ingestion.md`
- [Adding configurable JSON API ingestion](../../test/update_log/17_json_api_ingestion.md) `crawler/src/crawler/test/update_log/17_json_api_ingestion.md`
- [Closing structured-ingestion edge cases and verifying persistence](../../test/update_log/18_structured_ingestion_edges.md) `crawler/src/crawler/test/update_log/18_structured_ingestion_edges.md`
- [Reconciling the local and remote ingestion histories](../../test/update_log/19_ingestion_history_merge.md) `crawler/src/crawler/test/update_log/19_ingestion_history_merge.md`

**Indexer**

- [Developer's Eye indexer service + writer](../../../indexer/README.md) `crawler/src/indexer/README.md`
- [Developer's Eye: Indexer Analyzer](../../../indexer/docs/ANALYZER.md) `crawler/src/indexer/docs/ANALYZER.md`
- [Developer's Eye — Indexer: Builder](../../../indexer/docs/builder.md) `crawler/src/indexer/docs/builder.md`
- [Indexer configuration](../../../indexer/docs/config.md) `crawler/src/indexer/docs/config.md`
- [Indexer file responsibilities](../../../indexer/docs/file_task.md) `crawler/src/indexer/docs/file_task.md`
- [reporting.py — indexer coverage report](../../../indexer/docs/reporting.md) `crawler/src/indexer/docs/reporting.md`
- [Developer's Eye — Indexer: Selector](../../../indexer/docs/selector.md) `crawler/src/indexer/docs/selector.md`
- [Developer's Eye: Indexer service](../../../indexer/docs/service.md) `crawler/src/indexer/docs/service.md`
- [Developer's Eye: vector.py](../../../indexer/docs/vector.md) `crawler/src/indexer/docs/vector.md`
- [Developer's Eye: Transactional index writer](../../../indexer/docs/writer.md) `crawler/src/indexer/docs/writer.md`
- [Developer's Eye indexer operations](../../../indexer/operations.md) `crawler/src/indexer/operations.md`
- [Running the indexer tests](../../../indexer/tests/README.md) `crawler/src/indexer/tests/README.md`
- [Indexer test cases](../../../indexer/tests/test_case.md) `crawler/src/indexer/tests/test_case.md`

**Frontend (Next.js, admin)**

- [Developer’s Eye frontend](../../../../../frontend/README.md) `frontend/README.md`
- [Developer’s Eye — API and backend connector reference](../../../../../frontend/public/api-reference.md) `frontend/public/api-reference.md`
- [Running the frontend tests](../../../../../frontend/tests/README.md) `frontend/tests/README.md`
- [Frontend test cases](../../../../../frontend/tests/test_case.md) `frontend/tests/test_case.md`

**Other**

- [Faced problems](../../../../faced_problems.md) `crawler/faced_problems.md`
<!-- docs-nav:end -->
