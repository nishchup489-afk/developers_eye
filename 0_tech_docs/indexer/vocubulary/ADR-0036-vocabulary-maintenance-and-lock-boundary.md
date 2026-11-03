---
id: ADR-0036
title: Keep vocabulary maintenance transactional and rebuild it with a one-shot CLI
status: accepted
date: '2026-11-02'
area: indexer
feature: vocubulary
code:
- crawler/src/indexer/vocabulary.py
- crawler/src/indexer/vocabulary_rebuild.py
- crawler/src/indexer/writer.py
- crawler/src/crawler/worker/jobs/utility.py
supersedes: null
superseded_by: null
related:
- ADR-0002
- INC-0007
- EXP-0002
- EXP-0006
---

# ADR-0036: Keep vocabulary maintenance transactional and rebuild it with a one-shot CLI

## TL;DR

Maintain vocabulary as a projection of stored vectors, with a shared transaction advisory mutex and a one-shot rebuild command. Preserve the existing worker-style logs without introducing a permanent vocabulary worker.

## Context

The abandoned worker added duplicate selection/tokenization state. Incremental deltas simplify ownership but must cover every update/delete path and repair existing data. ADR-0002 establishes the underlying projection decision.

## Decision

The intended lock order is vocabulary mutex, then document rows in stable order, then term changes. Index upserts and crawler removals participate, but indexer remove_search_index currently omits the mutex (INC-0007). Rebuild streams stored vector lexemes, counts each term once per document, replaces counts in one transaction and logs completion only after commit. Stop crawler/indexer writers for an operational rebuild. CLI offers --once, progress and write-batch sizes, log level and failure exit status; it is not another recurring worker. A filter change requires a recount.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Global mutex and explicit rebuild | Simple consistency reasoning | Serializes writers and long maintenance | current strategy with known defect |
| Dedicated vocabulary worker | Can run separately | Lag, duplicate state and independent failure recovery | abandoned |
| Fine-grained term locks immediately | Potential concurrency | Much harder ordering/rebuild coordination | deferred until benchmarked |

## Why

Derived counts must change atomically with the indexed document set. A single coordination point is easier to audit now, but only works if all paths actually use it.

## Consequences

- Gained: Repairable derived state and consistent maintenance UX.
- Accepted limitations / tech debt: The bulk-increment loop overcounts and a deletion path skips the mutex; current counts are not guaranteed correct. Rebuild cannot prevent the buggy writer from drifting again.
- Dependencies: the governed code and linked feature overviews must evolve together.

## Invariants

- One document contributes at most one frequency unit per retained term.
- Index mutations and vocabulary deltas share a transaction.
- A successful rebuild log is emitted only after commit.

## Evidence

Code inspected at [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492). This is a retrospective record of the implementation, not a load-test result. Alternatives without a linked prototype are design comparisons, not experiments that were run. PRs [#4](https://github.com/nishchup489-afk/developers_eye/pull/4) and [#5](https://github.com/nishchup489-afk/developers_eye/pull/5) establish repair/CLI history; their descriptions explicitly did not verify live PostgreSQL tests.

- [`crawler/src/indexer/vocabulary.py`](../../../crawler/src/indexer/vocabulary.py)
- [`crawler/src/indexer/vocabulary_rebuild.py`](../../../crawler/src/indexer/vocabulary_rebuild.py)
- [`crawler/src/indexer/writer.py`](../../../crawler/src/indexer/writer.py)
- [`crawler/src/crawler/worker/jobs/utility.py`](../../../crawler/src/crawler/worker/jobs/utility.py)

Regression coverage to run when changing behavior (not a claim of a new test run):

- [`crawler/tests/indexer/test_vocabulary.py`](../../../crawler/tests/indexer/test_vocabulary.py)
- [`crawler/tests/indexer/test_vocabulary_rebuild_cli.py`](../../../crawler/tests/indexer/test_vocabulary_rebuild_cli.py)
- [`crawler/tests/crawler/worker/test_postgres_pipeline.py`](../../../crawler/tests/crawler/worker/test_postgres_pipeline.py)

## Revisit when

- Before trusting fuzzy frequency counts after repairing INC-0007.
- Mutex wait time dominates indexing/finalization or rebuild duration exceeds the maintenance window.

## Rules for future changes

- Fix incremental correctness before recounting and resuming writers.
- Do not reintroduce a permanent vocabulary worker without an ADR.
- Measure contention before replacing the mutex.
