# Fixing abandoned attempts and retry recovery

**Files involved:** worker runner/jobs/recovery/telemetry, scheduler repository, attempt writer/model, migration `d83a429ce034` and regression tests.

## The problem

Timeouts, crashes and exhausted storage retries could leave attempts unfinished. Expiration recovery cleared the URL lease without incrementing failures or delaying the next attempt.

## What changed

- Store the exact frontier lease on every new attempt.
- After a job failure, close its attempt in an independent transaction and use normal scheduler backoff if it still owns the claim.
- On lease expiration, close abandoned attempts, increment failures and schedule exponential backoff.
- Reconcile older unfinished attempts only while their target has no active lease.
- Prevent late checkpoints from replacing terminal attempt measurements.

Before: a timeout could remain unfinished while its URL immediately retried after expiration.

After: the attempt is failed and the URL receives failure backoff. A stale worker can close its own old attempt but cannot requeue another worker's newer claim.

If the database is unavailable, recovery is retried by the lease-expiration path after connectivity returns.

## Verification

Offline regression tests cover timeout accounting, claim ownership, preserved persistence errors, expired-lease backoff and historical reconciliation. The migration adds a nullable lease token, so existing history is preserved.
