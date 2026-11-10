.order_by(
    CrawlTarget.priority.desc(),
    CrawlTarget.next_fetch_at.asc(),
    CrawlTarget.id.asc(),
)
.limit(limit)
.with_for_update(skip_locked=True)

## Round robin made the second worker idle (2026-10-27)

**Problem.** After round-robin BFS claiming (commit `e019701`), `claim_targets()` picked each source with `FOR UPDATE OF source SKIP LOCKED`. A row lock lasts until the transaction commits, so while worker A was claiming from a source, worker B skipped that source completely. When it was the only source with due work, B got `[]` even with hundreds of URLs waiting, and the runner sleeps `--poll-seconds` after an empty claim. The worker test `test_concurrent_claims_atomic_writes_and_shared_source_budget` failed with 2 and 0 targets instead of 2 and 2. A benchmark draining 2000 targets from one source saw about 6,500 empty claims with 4 workers and 12,000 with 8, and adding workers made it slower (136/s with 1, 92/s with 4, 70/s with 8).

**Fix.** Don't lock the source row while claiming. Read the round-robin order once without a lock, take turns in memory, lock only the targets (`FOR UPDATE OF crawl_target SKIP LOCKED`), and write `last_claimed_at` once per source at the end, in ascending source id order (same lock order for every worker, so no deadlock). With 4 workers the same drain ran at about 480/s, and with 8 at about 570/s, with no empty claims.

**Lesson.** `SKIP LOCKED` on a "parent" row like `source` skips all of its children for everyone else until commit. Lock the rows that are actually being handed out (the targets), and keep shared bookkeeping writes short and in a fixed order.

Details: `0_tech_docs/crawler/scheduler-and-leases/ADR-0001-round-robin-claims-without-source-locks.md` and `EXP-0001-claim-path-concurrency-benchmark.md`. Tests: `crawler/tests/crawler/scheduler/test_concurrent_claims.py`.

## Search index test row without `code_vector` (2026-10-27)

**Problem.** `test_removed_page_invalidates_index_and_recovers_when_restored` inserted a `SearchIndex` row with only `search_vector`. `search_index.code_vector` is `NOT NULL` now, so the insert failed with `NotNullViolationError`.

**Fix.** The fixture now sets `code_vector=func.to_tsvector('simple', '')` as well. The indexer builds code vectors with the `simple` config, and this page has no code blocks.

## Search timeout that never fired on a cold server (2026-11-07)

**Problem.** While adding "Did you mean" tests, `npm run test:integration` hung for about 5 minutes at the existing `/api/search` timeout check. On a freshly started `next start` process, the first request to a FastAPI backend that never answered did not time out, while the second one returned 504 after 10 s. Logging showed axios's timeout signal did abort at 10 000 ms, but Next.js 16's patched `fetch` never settled.

**Fix.** `frontend/lib/axios.js` now gives the `backend` client an `abortableFetch` that races the fetch against its signal and rejects with the signal's reason (axios's `ETIMEDOUT`), so routes return 504 either way.

**Lesson.** A signal that aborts is not proof the request stopped: check that the promise actually settles. Test timeouts against a freshly started server, because the first request can behave differently.

Details: `0_tech_docs/frontend/search-experience/INC-0033-upstream-timeout-ignored-on-first-hung-request.md`.

## Spelling suggestions showed word stems (2026-11-07)

**Problem.** The vocabulary behind `/search/suggest` stores English stems (`configur`, `librari`), so a suggestion could look broken. Edit distance was measured against the stem, so `configuraton` got no suggestion at all, and `configuration` itself looked like a typo because only `configur` is stored. pg_trgm's 0.3 threshold also missed `pyhton` (similarity 0.27).

**Fix.** Rebuild readable words from each stem (stem + common suffixes, `i` back to `y`), keep only those PostgreSQL's `english_stem` reduces to the same stem, and measure distance to the typed word. A word whose stem is indexed counts as spelled correctly. The trigram threshold is lowered to 0.2 for this one transaction.

**Lesson.** A search vocabulary built from stems is not a dictionary. Anything shown to users has to go back through the same stemmer the index used.

Details: `0_tech_docs/backend/fuzzy-correction/ADR-0045-did-you-mean-with-surface-word-suggestions.md`.

## Ten-second searches from counting common words (2026-11-10)

**Problem.** At about 100k documents, nine evaluated searches took over 5 s (`HTTP 500 internal server error` 10.7 s). BM25 needs, for each query word, the number of documents that contain it. For common words like `python` or `error`, PostgreSQL chose a sequential scan of `search_index` over the GIN index, and that scan unpacks (detoasts) every stored `tsvector`: about 1 s per word.

**Fix.** The document-frequency query now runs with `enable_seqscan` off for that one statement (transaction-local, then restored), so it always reads GIN posting lists. On a 126k copy the counts are identical and take 18–67 ms instead of 0.97–1.83 s; whole cold searches dropped from 1–2 s to 61–275 ms. Slow searches are now logged with time per stage on the admin Search quality page.

**Lesson.** The planner prices rows, not the cost of unpacking large TOASTed values. When a count only needs "which documents contain this", make sure it stays on the index, and measure at the corpus size you plan to run.

Details: `0_tech_docs/backend/bm25-statistics/INC-0041-search-latency-from-detoasting-df-counts.md`, `EXP-0016-gin-only-document-frequency-counts.md`.
