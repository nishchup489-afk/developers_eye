# Scheduler test cases

Integration tests for `crawler.schedular.repository`. Four files are script-style (`python <file>`, with a `main()` and a selector event loop on Windows). Each one opens a real PostgreSQL transaction, creates a uniquely named temporary `Source` and `CrawlTarget` rows, and rolls everything back at the end. `test1_report.md` and `image.png` in this folder are an earlier run report. `test_concurrent_claims.py` is a pytest file instead, because it needs committed rows and two connections; `bench_claim.py` is a benchmark, not a test.

## test_repository.py

Claiming targets and recovering expired leases (`claim_targets`, `recover_expired_leases`). Setup: two queued, due targets with priority 10 and 5.

| Check | What it verifies |
| --- | --- |
| Claim highest priority | `claim_targets(limit=1, source_id=...)` returns the priority 10 target first. |
| Claim second | The next claim returns the priority 5 target. |
| Nothing left | A further claim for the source returns `[]`, since both are now leased. |
| Active leases untouched | `recover_expired_leases` returns `0` while leases are still valid. |
| Expired lease recovered | After moving one target's `lease_until` into the past, recovery returns `1`, that target goes back to `queued` with `lease_until` cleared, `failure_count` 1 and a retry in the future, and the other target stays `leased`. The test flushes before `refresh()`, because recovery changes ORM objects without flushing. |
| Reclaim recovered target | After making the recovered target due again, it can be claimed again (pinned with `source_id`, since round robin picks across all sources) and is `leased`. |
| Invalid parameters | `limit=0` and `lease_seconds=0` raise `ValueError`. |

## test_round_robin.py

Round-robin BFS claiming (`claim_targets`), 21 checks. How the claim works is in [REPOSITORY_README.md](../DOCS/REPOSITORY_README.md#how-claim_targets-picks-work-round-robin-bfs). `claim_targets()` looks across every source, so the test first disables all other sources inside its transaction; the rollback turns them back on. Each section creates its own sources so earlier ones cannot interleave.

| Section | What it verifies |
| --- | --- |
| 1. Rotation in one call | Sources A (3 due targets), B (2) and C (1), never claimed. `claim_targets(limit=6)` returns six targets from sources A, B, C, A, B, A. |
| 2. BFS inside a source | Source A's targets come out as priority 80 (depth 3), then priority 50 depth 0, then priority 50 depth 2. Source B gives depth 0 before depth 1. Every claimed target is `leased`. |
| 3. `last_claimed_at` | Set on A, B and C, and ordered C < B < A to match each source's last turn. A further claim returns `[]`. |
| 4. Least recently claimed first | D was last claimed 1 h ago and E 2 h ago, two targets each. Three `limit=1` calls pick E, D, E. |
| 5. Skipped sources | A disabled source with a due target and an enabled source whose only target is not due yet. `claim_targets(limit=5)` returns only D's remaining target; both skipped targets stay `queued` and both sources keep `last_claimed_at` empty. |
| 6. `source_id` filter | With another source holding due work, `source_id=H, limit=2` returns two targets, both from H, and `limit=10` then returns H's last one. |
| 7. Lease and validation | `lease_seconds=120` gives a `lease_until` about 120 s after the claim. `limit=0`, `lease_seconds=0` and `source_id=0` raise `ValueError`. |

Not covered here: a source skipped because another worker holds its row or all its due targets locked (`SKIP LOCKED`, the `unavailable` set). That needs two connections on committed rows, which these roll-back-only scripts avoid.

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

## test_concurrent_claims.py

Concurrent claiming on committed rows (pytest, 4 tests). Needs `TEST_DATABASE_URL` pointing at a dedicated database with `test` in its name. Each test creates its own sources and targets, disables other sources while it runs, and deletes its rows and re-enables the others afterwards. Why claims work this way: [ADR-0001](../../../../../0_tech_docs/crawler/scheduler-and-leases/ADR-0001-round-robin-claims-without-source-locks.md). All four tests fail on the first round-robin version (source row locked during the claim) and pass now.

| Test | What it verifies |
| --- | --- |
| Single source, overlapping claims | One source with 6 targets. A first transaction claims 3 and stays open while a second transaction claims. The second also gets 3, with no target in both, and all 6 end up `leased`. |
| Multi source, overlapping claims | Two sources with 4 targets each. Two overlapping `limit=2` claims each get exactly one target from each source, with no overlap. A third claim also gets one from each source. |
| Parallel drain, 1 x 60 | 4 workers loop claim-and-commit until nothing is due. Every target is claimed exactly once, and no worker gets `[]` while an unlocked due target exists. |
| Parallel drain, 6 x 10 | Same as above with 6 sources, and every source ends up with `last_claimed_at` set. |

A `lock_timeout` of 5 s on the test connections turns a lock wait that never ends into a failure instead of a hang.
