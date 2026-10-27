---
id: EXP-0001
title: Claim path latency and multi-worker drain, source-locked vs unlocked round robin
status: done
outcome: adopt
date: 2026-10-27
area: crawler
feature: scheduler-and-leases
informs: [ADR-0001]
---

# EXP-0001: Claim path latency and multi-worker drain

## Question
With round-robin claiming, does locking the `source` row for the whole claim transaction (`FOR UPDATE OF source SKIP LOCKED`) stop extra workers from helping when only one source has due work? And does removing that lock fix this without making a single claim slower?

## Why it matters
This decides whether `claim_targets()` needs more database coordination (advisory locks, a turn table) or whether dropping the source lock is enough. See ADR-0001.

## Setup
- Hardware / OS: cloud dev container, 4 vCPU, Linux. Client and database on the same machine.
- Versions: PostgreSQL 16.15, Python 3.13, SQLAlchemy 2.1.6, asyncpg 0.32.0.
- Data: synthetic `source` and `crawl_target` rows from `bench_claim.py`. All targets are queued, due, priority 50, depth 0 to 3. Other sources in the database are disabled during the run.
- Configuration: `claim_targets(limit=10, lease_seconds=300)`, a connection pool of 20, and migrations up to `5fc9efde409c`.

## Method
- Baseline: `claim_targets()` from commit `e019701` (source row locked with `FOR UPDATE SKIP LOCKED`, `last_claimed_at` written in the loop).
- Variable changed: `claim_targets()` from ADR-0001 (source order read without locks, target-only `SKIP LOCKED`, `last_claimed_at` written at the end in id order).
- Metrics:
  - **latency**: one worker, 200 runs of `BEGIN; claim_targets(limit=10); ROLLBACK`, p50 and p95;
  - **drain**: N workers loop `BEGIN; claim_targets(limit=10); COMMIT` with no sleep until nothing is due. Reports targets per second, and *empty claims while work left*: claims that returned `[]` while due, queued targets still existed. The drain also asserts that no target id is claimed twice.
- Data shapes: 1 source x 2000 targets (the "only eligible source" case) and 50 sources x 40 targets.
- Runs per variant: 2 full runs.

## Reproduce
From `crawler/`, against a migrated database with `test` in its name:
```
$env:BENCH_DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/developers_eye_test"
git show e019701:crawler/src/crawler/schedular/repository.py | Out-File -Encoding utf8 ..\repo_baseline.py
poetry run python src/crawler/schedular/tests/bench_claim.py ..\repo_baseline.py baseline
poetry run python src/crawler/schedular/tests/bench_claim.py src/crawler/schedular/repository.py current
```

## Results
Drain throughput in targets per second, with empty claims while work was left in brackets. Each cell shows run 1 / run 2.

| Data | Workers | Baseline (source lock) | ADR-0001 (no source lock) |
| --- | --- | --- | --- |
| 1 source x 2000 | 1 | 136 (0) / 143 (0) | 174 (0) / 185 (0) |
| 1 source x 2000 | 4 | 92 (6528) / 99 (6819) | 485 (0) / 478 (0) |
| 1 source x 2000 | 8 | 70 (12066) / 66 (12127) | 563 (1) / 580 (0) |
| 50 sources x 40 | 1 | 185 (0) / 74 (0) | 222 (0) / 329 (0) |
| 50 sources x 40 | 4 | 382 (0) / 269 (1) | 471 (1) / 449 (1) |
| 50 sources x 40 | 8 | 370 (3) / 256 (9) | 461 (2) / 449 (0) |

Single-worker `claim_targets(limit=10)` latency in ms, p50 / p95:

| Data | Baseline run 1 | Baseline run 2 | ADR-0001 run 1 | ADR-0001 run 2 |
| --- | --- | --- | --- | --- |
| 1 source x 2000 | 94.9 / 130.3 | 97.7 / 136.3 | 72.0 / 101.9 | 77.7 / 115.0 |
| 50 sources x 40 | 118.0 / 159.9 | 124.6 / 172.1 | 39.4 / 56.8 | 49.8 / 88.6 |

No duplicate claims in any run.

## Analysis
- The claim holds up. With one source, the baseline gets **slower** as workers are added: almost every claim by a worker other than the lock holder comes back empty (about 6,500 with 4 workers and 12,000 with 8 per 2,000 targets). In the real runner each empty claim means sleeping `--poll-seconds`, so the effect is much worse than these tight loops show. Without the source lock, 4 workers are about 2.7x and 8 workers about 3.2x faster than one, with no empty claims.
- With 50 sources the baseline still scales, because workers spread over different sources, but each claim is slower. It re-runs the source query (with its `EXISTS` subquery) and an `UPDATE source` for every target. ADR-0001 reads the source order once per call and writes `last_claimed_at` once per source, which is why single-claim latency also dropped (p50 118 to 39 ms on run 1).
- The 0 to 2 empty claims left with ADR-0001 are the end of the drain: the last few due rows are locked by other workers' open claims, which are about to commit them as leased. The regression test counts work left with `SKIP LOCKED`, so it does not count these.
- Limits: one machine, synthetic data, client on the same host, and only two runs. The baseline 1-worker number for 50 sources varied a lot between runs (185 vs 74/s). Absolute numbers will differ on a laptop; the gap between the two versions is what matters.

## Outcome
Adopt. Dropping the source row lock removes the starvation of extra workers and makes single claims faster. No extra coordination (advisory locks, a turn table) is needed at current scale. The trigger to revisit is in ADR-0001.
