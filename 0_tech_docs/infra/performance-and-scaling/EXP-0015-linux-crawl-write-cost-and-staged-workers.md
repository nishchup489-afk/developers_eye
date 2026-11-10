---
id: EXP-0015
title: Measure Linux crawl write costs and stage workers before further redesign
status: done
outcome: adopt
date: 2026-11-09
area: infra
feature: performance-and-scaling
informs: [ADR-0055, ADR-0042]
---

# EXP-0015: Linux crawl write costs and staged workers

## Question and setup

Can adjacent telemetry checkpoints be combined without losing failure evidence,
and does increasing worker processes preserve shared politeness?

Ubuntu 26.04 under WSL, PostgreSQL 18.6, Python 3.14, separate migrated
`developers_eye_checklist_load_test` database. Real worker processes execute
claim, policy, parsing, processing and finalization. DNS/HTTP are fake: no
requests go to public sites. Twelve hosts, 300 pages each, 100 ms minimum
request-start interval, 15 ms simulated network latency with jitter, eight
concurrent slots per process, twenty seconds per run. Processes run sequentially
by configuration, not simultaneously with another load run.

Baseline source: `74d63a4`; telemetry change: `9a28923`. The baseline already
contains strict worker-exit validation and database counters. All comparisons
allow at most 5 ms scheduler/timer tolerance, and report request overlap separately.

## Reproduce

After installing the crawler and migrating an isolated benchmark database, from
`crawler/` (replace only the test database URL for the local server):

```sh
export PGHOST=/var/run/postgresql
export BENCH_DATABASE_URL=postgresql+asyncpg:///developers_eye_checklist_load_test
python tests/benchmarks/fake_web_load.py --workers 1 --concurrency 8 \
  --hosts 12 --pages 300 --gap 0.1 --latency-ms 15 --seconds 20
# Repeat with --workers 2, 4, and 8, after the previous run exits.
```

The harness checks the actual database name, removes only its own `fakeweb-*`
sources, disposes worker engines, and fails if any worker exits unsuccessfully
or any gap/overlap violation occurs. Never run it against an application database.

## Results

| Version | Workers | Requests | Requests/s | Committed transactions/request | Updated tuples/request | Gap violations / overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Before | 1 | 1,034 | 52.10 | 8.88 | 10.03 | 0 / 0 |
| Batched telemetry | 1 | 1,089 | 54.79 | 7.91 | 5.00 | 0 / 0 |
| Batched telemetry | 2 | 1,166 | 58.77 | 8.04 | 5.03 | 0 / 0 |
| Batched telemetry | 4 | 1,186 | 59.64 | 8.20 | 5.07 | 0 / 0 |
| Batched telemetry | 8 | 1,344 | 67.41 | 8.43 | 5.08 | 0 / 0 |

Every child exited zero. Raw reports preserve database snapshots, table sizes,
HOT/dead tuple counters, and child exit codes:
[before](../../../backend/reports/checklist/crawl-linux-before.json),
[one](../../../backend/reports/checklist/crawl-linux-after-1.json),
[two](../../../backend/reports/checklist/crawl-linux-after-2.json),
[four](../../../backend/reports/checklist/crawl-linux-after-4.json),
[eight](../../../backend/reports/checklist/crawl-linux-after-8.json).

Transaction counts include all commits in the dedicated database during the
measurement interval, including scheduling/polling and observation overhead.
They are not a per-success-path SQL trace. Updated tuple counts are PostgreSQL
statistics deltas, not bytes or physical disk writes. Short single runs with
jitter and retained table history do not establish a statistically significant
throughput gain or sustained production capacity. The theoretical host-start
ceiling here is 120 requests/s. More workers give modest gains and more polling
cost; this does not justify thirty processes. This harness does not exercise
public DNS/TLS, robots downloads, real bandwidth, or full CLI heartbeat startup.

## Adopted change

Adopt ADR-0055: batch adjacent CPU stage events and write the terminal attempt
summary with the terminal state update. PostgreSQL regressions verify events,
normal processing failures, rollback, lease fencing, and terminal atomicity.
Successful PARSE progress becomes durable after PROCESS finishes/fails; a hard
crash during processing can leave only FETCH evidence until recovery. Keep this
visibility tradeoff explicit. No event-loop policy was changed for this Linux run.

## Other scaling decisions

These are evaluated alternatives, not implemented caches or counters.

| Proposal | Evidence and decision | Revisit condition |
| --- | --- | --- |
| Maintained source frontier counters | Current largest-source count scans 11,385 rows in 10.742 ms using the source index. Keep exact counts and existing budget advisory locks; a counter spanning insert/delete/cascade/reconciliation paths has not been verified safe. | Measure source-budget count frequency/lock waits under representative discovery, then prove atomic increments/decrements and reconciliation. |
| Reusable pinned HTTP pools | `fetcher/client.py` deliberately binds one request URL and approved IP set. Generic hostname pooling can reuse a socket after approval changes. Keep request-scoped transport. | Demonstrated DNS/TLS handshake bottleneck plus a bounded pool keyed by origin and approved IP set, lifecycle eviction, and rebinding/redirect/TLS regression coverage. |
| DNS TTL cache | `getaddrinfo` does not supply authoritative DNS TTL; no measured DNS bottleneck here. Retain fresh public-IP validation and pinning. | TTL-aware resolver, bounded/expiring entries, all-address validation, failure semantics, and measured benefit. |
| Conditional GET / 304 reuse | Existing response handling accepts 304; the one-hop request contract lacks validator headers and there is no persisted validator lifecycle. Keep full fetches. | Specify validator ownership across acquisition producers/redirects, freshness, tombstones and reindex behavior; test 200/304 and changed-resource cases before rollout. |
| `crawl_target` fillfactor | Live local stats show 318 HOT updates of 240,081 total (0.13%); fake workload has zero HOT target updates. Frequently updated state/due/lease fields are indexed, so reducing fillfactor alone cannot make those updates HOT. Leave storage parameters unchanged. | Controlled fillfactor comparison of space, vacuum, update latency, index churn and throughput. |
| Autovacuum and event retention | Local DB uses default 0.2 vacuum / 0.1 analyze scales; `deploy/postgresql.conf` already specifies 0.05 / 0.02. Do not confuse the two. Existing bounded purge supports 14-day retention; zero local events are old enough. No application events deleted. | Measure deployed vacuum lag/dead tuples and schedule the existing maintenance command with the chosen operational retention policy. |

Read-only current-frontier/table evidence:
[frontier and retention](../../../backend/reports/checklist/frontier-and-retention.json).
This is a local snapshot, not a production tuning result. Local PostgreSQL has
200 max connections; the separate Linux test server has 100. Neither changes
the earlier deployment pool-budget decision.

## Source breadth

The current registry already contains 380 enabled sources: 218 websites, 161
feeds, and one API, spanning 316 distinct base hosts. All pass initial configured
allowed-host/path-scope checks. The old five-source blocker is stale; no source
was added by this experiment. Configured page budgets sum to 598,245, so this
inventory does not prove two-million-page acquisition capacity. See
[source inventory](../../../backend/reports/checklist/source-inventory.json).
Every actual request must still pass robots, public-IP pinning, redirect checks,
and shared host pacing. Static configuration eligibility is not a site-specific
permissions review; no public crawl or production deployment was initiated.

## Conclusion and next gate

Adopt the bounded write reduction and retain the tested safety boundaries.
Advance beyond eight workers only after representative sustained ingestion,
real per-stage network timing, connection budgets and database waits justify it.
The checklist's public-release load/deployment gates remain open.
