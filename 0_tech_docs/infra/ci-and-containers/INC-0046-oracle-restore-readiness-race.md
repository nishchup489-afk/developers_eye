---
id: INC-0046
title: Oracle restore check connected before PostgreSQL finished initialization
status: resolved
date: 2026-11-17
severity: medium
area: infra
feature: ci-and-containers
code: [deploy/restore-test.sh, deploy/docker-compose.yml, deploy/tests/smoke_stack.py]
fix_commits: []
related: [EXP-0018]
---

# INC-0046: Oracle restore check connected before PostgreSQL finished initialization

## Signature

```text
createdb: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: No such file or directory
```

## Summary

The Oracle container readiness job built the frontend and wrote a backup from
the isolated PostgreSQL 18 stack. The restore script exited before loading the
backup, so the workflow failed and skipped its remaining checks.
[Failed job](https://github.com/nishchup489-afk/developers_eye/actions/runs/44192609045/job/134425655969)

## Expected vs actual

- Expected. The restore script waits for the test database to finish startup,
  then loads the dump and checks its contents.
- Actual. The readiness probe succeeded during initialization. The following
  `createdb` command found the socket missing.

## Root cause

The PostgreSQL image starts a temporary server on a Unix socket to initialize
the data directory. The script's default `pg_isready` probe could report success
against that server, which shuts down before the final server starts. The
Compose database health check had the same socket-based readiness condition
before migrations.
[PostgreSQL image entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh#L431-L447)

## Resolution

Probe TCP on `127.0.0.1` inside each database container. Only the final server
listens on TCP. The restore commands can then use the container's local
socket, and Compose can start migrations after the database is ready.

## Prevention

- The Oracle readiness workflow still runs the real backup and restore scripts
  against fresh containers and checks restored rows.
- Keep the wait bounded so a database startup failure still fails the job.

## Rules for future changes

- Probe TCP for readiness of fresh PostgreSQL containers so initialization
  cannot satisfy the probe (INC-0046).
