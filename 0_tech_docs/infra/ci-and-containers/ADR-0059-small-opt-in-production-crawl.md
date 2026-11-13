---
id: ADR-0059
title: Run a small opt-in production crawl bounded by source caps and a disk guard
status: accepted
date: 2026-11-13
area: infra
feature: ci-and-containers
code: [deploy/docker-compose.yml, deploy/cap-sources.sh, deploy/disk-guard.sh, deploy/postgresql-12gb.conf]
related: [ADR-0058, EXP-0021, EXP-0022]
---

# ADR-0059: Small opt-in production crawl

## TL;DR
The Oracle VM serves an existing corpus first and crawls only on purpose: one
crawler with two slots behind a `crawl` Compose profile. Corpus size is bounded by
per-source `max_pages` scaled to a document budget, and a cron guard stops the
crawler when disk or database limits are crossed.

## Context
The deploy crawler ran 40 concurrent jobs and started with every `docker compose up`.
The only hard size limit is a source's `max_pages` (default 10,000), which caps how
many URLs that source can ever queue. The seeds add up to about 700K URLs.
`ADMIN_TARGET_DOCUMENTS` and `ADMIN_DB_BUDGET_GB` drive dashboard warnings only.
The VM is a free-tier box whose disk and RAM are shared with search.

## Decision
- `crawler` is in profile `crawl`, runs `--concurrency 2 --batch-size 2`, and uses
  `ADMIN_HOST_MIN_INTERVAL_SECONDS` (default 2 s) as its per-host gap.
- `indexer-0` runs batch 100 x concurrency 2. Worker pools are 2 + 2; API 8 + 2.
- `cap-sources.sh` scales each enabled source's `max_pages` down in proportion so the
  total fits `CRAWL_MAX_DOCUMENTS` (default 150K, floor 20 per source). It can park
  never-fetched page targets above the new cap as `disabled`; it deletes nothing.
- `disk-guard.sh` runs from cron. It stops only the crawler when `/data` or `/` free
  space, database size or the document estimate crosses its limit, or when the
  database cannot be read. It never restarts the crawler.
- `POSTGRES_CONFIG=postgresql-12gb.conf` and `POSTGRES_SHM_SIZE=3gb` fit a 12 GB VM.

## Options considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| A. Data caps + host-side guard, deploy files only | No app code change; reversible; works today | Guard is polled, not transactional | chosen |
| B. Global document/disk check inside the claim query | Exact, no cron | App change and tests on the hot claim path | later, if A proves too coarse |
| C. Crawl with `--once` batches from cron | Simple bound per run | Still no total bound; restarts reseed | rejected: does not cap size |

## Why
Concurrency sets pace, not size: two slots still fetch about 80K pages a day. The
size bound has to come from the frontier cap, which already exists and is enforced
under a per-source advisory lock. Seeding uses `ON CONFLICT DO NOTHING`, so a lowered
cap survives restarts. The guard covers what caps cannot: WAL, logs, attempts and
images on the same disks.

## Consequences
- Gained: a fresh `docker compose up -d` serves search without crawling; crawl size is
  predictable; running out of disk stops ingestion before it stops Postgres.
- Accepted: `crawl_attempt` still gains a row per recrawl and is not purged; the guard
  catches its growth only through database size. Caps live in the database, so they
  must be reapplied after a restore or a new seed.
- Depends on this: the go-live guide (`deploy/GO_LIVE.md`) and the smoke test, which
  renders the `crawl` profile.

## Invariants
- `docker compose config --services` without `--profile crawl` does not list `crawler`.
- The crawler's `--min-interval-seconds` equals `ADMIN_HOST_MIN_INTERVAL_SECONDS`.
- `cap-sources.sh` never raises a cap and never deletes rows.
- `disk-guard.sh` never starts a service.
- Steady-state pool maxima stay below `max_connections` minus backup/admin reserve.

## Evidence
- Measured: `cap-sources.sh` and `disk-guard.sh` were run against a PostgreSQL 16 test
  database with a stubbed `docker`; compose rendered with and without the profile and
  with the 12 GB settings. Not yet run on the Oracle VM.
- Assumed: ~11.6 MB per 1K documents (EXP-0022), so 150K documents is roughly 2 GB.

## Revisit when
- The corpus target rises above ~500K or more than one crawler host is used.
- `crawl_attempt` exceeds 20% of database size.
- The guard stops the crawler more than once a week.

## Rules for future changes
- Do not add the crawler back to the default profile without a new ADR.
- Raise concurrency only together with the connection-pool math in `deploy/README.md`.
- Reapply `cap-sources.sh --apply` after every restore or reseed.
