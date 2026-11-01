---
id: ADR-0008
title: Indexer finds work by comparing document and index freshness, with no queue or lease table
status: accepted
date: 2026-10-31
area: indexer
feature: freshness-selection
code:
  - crawler/src/indexer/selector.py:select_index_candidates
  - crawler/src/indexer/selector.py:select_removal_candidates
  - crawler/src/indexer/selector.py:_outdated_index_condition
  - crawler/src/indexer/writer.py:persist_search_vectors
  - crawler/src/indexer/writer.py:remove_search_index
  - crawler/src/indexer/worker/runner.py
supersedes:
superseded_by:
related: [ADR-0004, ADR-0009, ADR-0002]
---

# ADR-0008: Indexer work is derived from freshness, with no queue or lease table

## TL;DR
The indexer does not have a job queue. Each poll it runs a read-only query for available documents whose `search_index` row is missing, older than `document.updated_at`, or built with another index version, and a second query for index rows whose document is gone or unavailable. A candidate is only a hint: the writer locks the `document` row `FOR UPDATE`, checks that it is still the revision the candidate was built from, and only then upserts or deletes. Work can never be lost, and a stale build can never overwrite a newer one.

## Context
The crawler writes `document` rows; the indexer turns them into `search_index` rows (two tsvectors and a hash). The crawler already used a lease-based queue for URLs (ADR-0004), so the obvious move was a second queue table, or a trigger that enqueues document ids on change.

What the indexer needs is different from the crawler:
- The "work" is fully described by the current database state: a document either has an up-to-date index row or it doesn't.
- Index builds are idempotent and cheap compared with a fetch (milliseconds of CPU and one upsert).
- A queue would have to be kept in step with every path that changes a document, including the crawler's 404/410 and `noindex` paths, manual SQL and future maintenance scripts.

> **Question for nish:** did you consider a trigger-fed queue table or `LISTEN/NOTIFY` for the indexer? If yes, note why you dropped it. If the reason was "the crawler queue was enough work already", that is a fine reason to write down.

## Decision
- **Freshness contract.** Every change to an index-relevant `document` field updates `document.updated_at`. `search_index.indexed_at` is written only by a successful build. `search_index.indexed_hash` starts with `v<INDEXER_INDEX_VERSION>:` (ADR-0009). `document.last_seen_at` does not trigger indexing.
- **Index candidates** (`select_index_candidates`): `document LEFT JOIN search_index` where `is_available` and (`search_index` row missing OR `indexed_at < updated_at` OR `indexed_hash NOT LIKE 'v<version>:%'`), `ORDER BY document.id`, `LIMIT batch_size`, keyset paged by `document.id > cursor`.
- **Removal candidates** (`select_removal_candidates`): `search_index LEFT JOIN document` where the document is missing or `is_available = false`, ordered by `document_id`.
- **No reservation.** The selector never locks, commits or marks rows. Two indexer workers can select the same document.
- **Writer revalidation** (`persist_search_vectors`): in one transaction, take `lock_vocabulary()` (ADR-0002), `SELECT ... FOR UPDATE` the document, return `STALE` if it is missing, unavailable, moved to another source, or `updated_at` differs from the candidate's `source_updated_at`; return `UNCHANGED` if the stored hash matches and `indexed_at >= updated_at`; otherwise upsert and return `INDEXED`.
- **Removal revalidation** (`remove_search_index`): lock the document; if it exists and is available, return `STALE` (it came back), otherwise delete the index row.
- **Loop** (`indexer.worker.runner`): each cycle selects one batch of each kind, runs them under a semaphore (`INDEXER_CONCURRENCY`, default 2), advances each cursor to the last id seen and resets it to 0 when a page comes back short; sleeps `INDEXER_POLL_SECONDS` (10 s) when there is nothing to do.
- Hard-deleted documents need no removal work: `search_index.document_id` has `ON DELETE CASCADE`.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Derive work from freshness columns; writer locks and revalidates | Nothing to keep in sync; can't lose work; restart-safe; reindex is "change the version" | Polling scans; two workers may build the same document; no failure memory | chosen |
| B. Queue table with leases (like `crawl_target`) | Exactly-once-ish dispatch; failure counts and backoff | Must be fed by every document change path; a missed enqueue is a silently stale index | rejected |
| C. Trigger on `document` that enqueues ids | Never misses a change made through SQL | Logic in triggers; still a queue to drain and lease | rejected |
| D. `LISTEN/NOTIFY` push | Low latency | Notifications are lost while no listener is connected, so a scan is needed anyway | rejected as the main mechanism |
| E. Index inside the crawler's write transaction | Index always current | Slows crawling; couples two pipelines; a vector bug blocks crawling | rejected |

## Why
- **Correctness.** The source of truth is the data itself. A crash, restart or bug in the runner cannot leave a document unindexed, because the next scan finds it again. The `FOR UPDATE` plus `updated_at` check in the writer means a build from an old snapshot returns `STALE` instead of overwriting a newer index.
- **Simplicity.** No extra table, no lease expiry, no recovery code. Reindexing is a version bump or the `reindex:pending` marker (ADR-0009).
- **Performance.** Keyset pagination on `document.id` avoids `OFFSET`. Builds are short, so occasional duplicate work between workers is cheap; the writer turns the loser into `UNCHANGED` or `STALE`.

## Consequences
- Gained: the index converges to the documents without any bookkeeping, and an operator can see what is pending with one SQL query.
- Accepted limitations:
  - **No failure backoff.** A document that always fails to build (for example a validation error) is selected again every cycle, forever, and wastes a slot each time. Its failures are only in the logs.
  - The candidate query scans `document` joined to `search_index` every poll. Its cost grows with the number of documents, not with the amount of work.
  - Multiple indexer workers do not split work; they compete for it.
  - Latency from crawl to searchable is up to one full scan plus `poll_seconds`.
- What depends on this: the crawler must bump `document.updated_at` whenever it changes indexed content; ADR-0002 relies on the writer transaction for vocabulary deltas; ADR-0009 relies on the version prefix being part of the candidate predicate.

## Invariants
- Any change to `title`, `description`, `body`, `headings`, `code_blocks`, `tags`, `document_type`, `canonical_url`, `source_id` or `is_available` also sets `document.updated_at`.
- The selector never writes or locks.
- The writer never upserts without first locking the document row and checking `updated_at` equals the candidate's.
- A removal never deletes the index of a document that is currently available.

## Failure modes
- Crawler changes content without touching `updated_at`: the index stays stale and nothing reports it. The freshness contract above is the only guard.
- Poison document: reselected every poll (see Consequences). Visible only in logs.
- Concurrency of two writers on the same document and "document changes while the writer waits for the lock" are handled by the design, but not covered by tests (see `crawler/src/indexer/README.md`, handoff gap 4).

## Evidence
- Tests: `crawler/src/indexer/tests/test_selector.py`, `test_service_writer.py` and `test_indexer.py` (Postgres lifecycle: new, unchanged, updated, unavailable, revived, hard-deleted documents; 152 indexer tests at `172b30f`).
- Measured: none (no scan cost or throughput numbers).
- Commits: `7faee9a` (selector), `99061a1` (selector query fix), `5d7ffcd` (writer and service), `0aedb4c` (runner, reporting, reindex).

## Revisit when
- The candidate query takes more than about 1 s per poll, or `document` passes roughly a million rows. Consider a partial index or a "dirty" flag column set by the crawler.
- Poison documents show up in the logs repeatedly. Add a failure count and backoff (a small `index_failure` table keyed by document id and `updated_at`).
- More than one indexer worker is needed for throughput. Split by `document_id % N` or add `FOR UPDATE SKIP LOCKED` claiming.

## Rules for future changes
- Every code path that changes indexed `document` fields must set `updated_at`.
- Do not make the selector write or lock anything; reservations belong in a new design and a new ADR.
- Do not upsert `search_index` outside `persist_search_vectors()`; keep the lock and the `updated_at` check.
- Keep passing: `indexer/tests/` (with `TEST_DATABASE_URL` for `test_indexer.py`).
