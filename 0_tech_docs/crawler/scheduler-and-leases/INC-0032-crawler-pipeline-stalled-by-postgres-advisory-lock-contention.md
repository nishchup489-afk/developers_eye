# INC-0032: Crawler Pipeline Stalled by PostgreSQL Advisory-Lock Contention

**Date:** November 2, 2026  
**System:** Developer's Eye  
**Affected components:** Crawler Worker, Indexer, Vocabulary Synchronization, PostgreSQL  
**Category:** Concurrency / Database Lock Contention / Performance Degradation  
**Status:** Root-cause hypothesis identified; remediation not yet verified

## Problem

Crawler workers continued fetching, parsing, and processing documents but repeatedly failed to finalize their jobs before the configured 240-second timeout.

The PostgreSQL frontier contained 56,391 eligible URLs, and three crawler workers remained online.

## Evidence

- Six PostgreSQL sessions were waiting on `pg_advisory_xact_lock`.
- Blocking backend PID `27344` was executing a bulk `INSERT INTO search_terms`.
- Waiting sessions had accumulated approximately 155 seconds of query time.
- The crawler monitoring snapshot recorded 106 timeouts during the seven-day reporting window.
- Successful fetch and parse events were observed without corresponding successful finalization.

## Root Cause Analysis

The vocabulary synchronization implementation contains a write-amplification defect in `indexer/vocabulary.py`.

Inside `synchronize_vocabulary()`, the implementation repeatedly upserts the entire collection of newly added terms while iterating over individual terms.

For N newly added terms, this can generate O(N²) term-level write operations instead of O(N).

The indexer and crawler share a transaction-scoped PostgreSQL advisory lock for vocabulary consistency. Excessive vocabulary writes can prolong lock ownership, blocking crawler finalization transactions.

The lock contention is confirmed by SQL diagnostics. The repetitive-upsert defect is confirmed in code. The precise blocking transaction's origin still requires verification.

## Impact

- Severe reduction in successful crawler throughput.
- Repeated 240-second job timeouts.
- Delayed document persistence and frontier progression.
- Potentially inflated vocabulary document-frequency statistics.
- Accumulation of pending crawl targets.

## Remediation

1. Correct vocabulary synchronization to apply each document-frequency increment exactly once.
2. Verify and eliminate long-running lock-holding transactions.
3. Rebuild vocabulary frequencies from indexed documents with crawler and indexer writers stopped.
4. Resume workers and verify successful finalization.
5. Add regression tests, lock-wait monitoring, and transaction-duration metrics.

## Prevention

Maintain bounded vocabulary write batches, minimize transaction durations, and alert on excessive advisory-lock waits and crawler finalization latency.