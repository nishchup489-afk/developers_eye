# Connecting the deadlock retry helper

**Files involved:** `worker/jobs/jobs.py` and `worker/tests/test_deadlock_retry.py`.

## The problem

The existing retry helper was defined but never called. `process_job()` still called `_finalize()` directly, so the first PostgreSQL deadlock failed the job.

## What changed

Wrap finalization in a callable and pass it to the existing bounded retry helper. Each retry opens a fresh transaction and rechecks lease ownership. Fetching, parsing and processing are not repeated.

Before: first `40P01` error escaped.

After: retry finalization up to four times, with exponential delay and jitter. Other database errors and cancellation still propagate immediately.

## Verification

Regression tests cover eventual success, retry exhaustion, non-deadlock errors and cancellation. Existing pipeline tests exercise the connected path.
