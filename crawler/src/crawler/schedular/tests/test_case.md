# Scheduler test cases

Integration tests for `crawler.schedular.repository`. All three files are script-style (`python <file>`, with a `main()` and a selector event loop on Windows). Each one opens a real PostgreSQL transaction, creates a uniquely named temporary `Source` and `CrawlTarget` rows, and rolls everything back at the end. `test1_report.md` and `image.png` in this folder are an earlier run report.

## test_repository.py

Claiming targets and recovering expired leases (`claim_targets`, `recover_expired_leases`). Setup: two queued, due targets with priority 10 and 5.

| Check | What it verifies |
| --- | --- |
| Claim highest priority | `claim_targets(limit=1)` returns the priority 10 target first. |
| Claim second | The next claim returns the priority 5 target. |
| Nothing left | A further claim for the source returns `[]`, since both are now leased. |
| Active leases untouched | `recover_expired_leases` returns `0` while leases are still valid. |
| Expired lease recovered | After moving one target's `lease_until` into the past, recovery returns `1`, that target goes back to `queued` with `lease_until` cleared, and the other target stays `leased`. |
| Reclaim recovered target | The recovered target can be claimed again and is `leased`. |
| Invalid parameters | `limit=0` and `lease_seconds=0` raise `ValueError`. |

## test_complete_target.py

Successful completion (`complete_target`), 12 checks. Setup: three leased targets with `failure_count=3`, two with an active lease and one with an expired lease.

| Check | What it verifies |
| --- | --- |
| 1. Success | Completing with the matching active lease returns `True`. |
| 2. State | `leased` becomes `queued`. |
| 3. Lease cleared | `lease_until` is `NULL`. |
| 4. Fetch time | `last_fetched_at` is set. |
| 5. Next crawl | `next_fetch_at` is `last_fetched_at + 86400` seconds (within 2 s). |
| 6. Failures reset | `failure_count` goes back to `0`. |
| 7. Duplicate | Completing the same target again returns `False`. |
| 8. Mismatched lease | A wrong `expected_lease_until` returns `False` and leaves the target `leased`. |
| 9. Expired lease | An already-expired lease returns `False` and leaves the target `leased`. |
| 10 to 12. Validation | Target ID `0`, a crawl interval of `0`, and a timezone-naive lease timestamp raise `ValueError`. |

## test_fail_target.py

Failure handling and retry backoff (`calculate_retry_delay`, `fail_target`). Uses the database `now()` as the reference time. Setup: six leased targets with failure counts 0, 2, 6, 20, plus one for a stale lease and one with an expired lease.

| Section | What it verifies |
| --- | --- |
| Exponential backoff | `calculate_retry_delay` gives 60, 120, 240, 480, 960, 1920 s for failures 1 to 6, and is capped at 3600 s for 7, 8, and 10. |
| First failure | Returns `True`, sets `state` to `queued`, clears the lease, increments `failure_count` 0 to 1, schedules a retry 60 s out, and leaves `last_fetched_at` unchanged. |
| Third failure | Count goes 2 to 3 and the retry is 240 s out. |
| Delay cap | The seventh failure retries after 3600 s; at 21 failures the counter keeps increasing but the delay stays at 3600 s. |
| Lease ownership | A duplicate failure report returns `False` and does not increment the count. A mismatched or expired lease returns `False` and leaves the target `leased` with count `0`. A nonexistent target ID returns `False`. |
| Parameter validation | `calculate_retry_delay` rejects `failure_count=0`, `base_delay_seconds=0`, and a max delay below the base. `fail_target` rejects target ID `0`, a zero base delay, a max below the base, and a timezone-naive lease, all with `ValueError`. |
