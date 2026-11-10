---
id: ADR-0055
title: Batch adjacent CPU checkpoints and write full attempt summaries at completion
status: accepted
date: 2026-11-09
area: crawler
feature: monitoring-and-telemetry
code: [crawler/src/crawler/worker/telemetry.py, crawler/src/crawler/worker/jobs/jobs.py, crawler/src/crawler/writer/attempts.py]
supersedes:
superseded_by:
related: [ADR-0020, EXP-0008]
---

# ADR-0055: Fewer checkpoint transactions and summary rewrites

## TL;DR

Commit adjacent PARSE/PROCESS observations in one short transaction. Successful
progress appends events without rewriting the growing attempt JSON; finalization
writes the complete summary in the same UPDATE that finishes the attempt.
Failure checkpoints retain their partial diagnostic snapshots.

## Context

Each successful crawl committed PARSE and PROCESS separately, repeatedly wrote
the same growing JSON summary, then updated the terminal summary and finished
the attempt in two UPDATE statements. Fake-web Linux runs flatten as worker
count rises, so reduce avoidable database work before adding processes.

## Decision

- Keep the pre-fetch attempt commit and independent FETCH progress checkpoints.
- Batch adjacent CPU-stage events after processing. A processing exception emits
  successful PARSE plus failed PROCESS together; a parse exception emits PARSE failure.
- Successful checkpoints store event details only. Failed/blocked checkpoints
  still persist the partial attempt snapshot for recovery/diagnosis.
- Pass `telemetry` to `finish_attempt` so terminal fields and full summary use one
  guarded UPDATE. Finalization and stale-outcome summaries retain atomicity.
- Network waiting remains outside database transactions. Monitoring failure
  remains best-effort and cannot turn valid acquisition into failure.

## Options considered

| Option | Benefit | Cost | Verdict |
| --- | --- | --- | --- |
| Batch CPU stages and terminal summaries | One fewer success-path checkpoint transaction; fewer JSON rewrites | PARSE visibility waits until PROCESS completes/fails | Chosen |
| Buffer all telemetry until shutdown | Fewer transactions | Loses in-progress and crash evidence | Rejected |
| Remove stage events | Lower storage | Loses the admin timeline and failure localization | Rejected |

## Why

The adjacent stages perform local CPU work, unlike network fetches. Their event
payloads remain intact and ordered. A hard crash during processing can leave only
FETCH evidence until lease recovery; this visibility tradeoff is explicit.

## Consequences

In-progress attempt JSON is not a live complete summary. Read stage events for
progress; terminal attempt telemetry contains the full result. Event retention
policy is unchanged. Failure diagnostics still survive a rolled-back final write.

## Invariants

- No database connection is held across network waits.
- PARSE success is retained when PROCESS fails normally.
- Terminal telemetry and finished_at/outcome commit together.
- Lease fencing, noindex/tombstone, rollback, retry and recovery tests remain passing.

## Evidence

Native worker/writer regressions passed, including real PostgreSQL event visibility,
failure snapshots, and atomic terminal summaries. Linux before/after write counters
are recorded separately in the crawl experiment; do not infer a throughput gain
from statement counting alone.

## Revisit when

CPU processing becomes long enough to require a separately durable PARSE checkpoint,
or measured event retention/writes dominate after this reduction.

## Rules for future changes

- Keep failure snapshots and per-stage event details when reducing write traffic.
- Preserve the explicit PARSE visibility/crash tradeoff and terminal atomicity.
