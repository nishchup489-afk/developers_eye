---
id: EXP-0018
title: Verify local Oracle containers and authenticated Vercel ingress
status: done
outcome: adopt
date: 2026-11-10
area: infra
feature: ci-and-containers
informs: [ADR-0058]
---

# EXP-0018: Local Oracle topology verification

## Question

Does the repository's proposed Vercel-to-Oracle API hop reject direct/spoofed
requests while preserving per-visitor search limits, service-key admin access,
real search, restoration and async process cleanup?

## Setup and method

Application suite on Windows/PostgreSQL 18.3/Python 3.14/Node 24.15.0. A fresh
Linux Git clone under Ubuntu 26.04/WSL builds the Python container and runs
Docker PG18.6, FastAPI and Caddy. The optional real frontend is installed with
`npm ci` and built using the official Node 24.15.0. Use generated credentials,
random loopback HTTP port, unique container/network/volume names, a temporary
database and one synthetic document. No real env file or public crawler is used.

The smoke DB uses 128 MB shared buffers and 30 connections; it does not validate
the production profile's 6 GB buffers, 24 GB memory sizing, block-storage
performance or cloud network. Its data directory is temporary local storage,
not proof that an Oracle block volume is mounted.

## Results

| Check | Result |
| --- | --- |
| Full application runner | 12 suites, 1,390 passed, zero failures/skips |
| Backend/crawler/indexer | 602 / 544 / 192 passed |
| Other frontend lint/type/build/unit/HTTP checks | 52 passed |
| Container image and PG18 empty migration | Passed |
| Public health, missing/wrong edge credential | 200 / 403 / 403 |
| Unauthenticated direct private API | 403 |
| Authenticated docs/OpenAPI | 404 |
| Same visitor twice / different visitor | 200 then 429 / 200 |
| Malformed authenticated visitor identity | 400 |
| Admin edge key only / both independent keys | 401 / 200 |
| Actual Next.js → Caddy → FastAPI → PostgreSQL | Live indexed result; runtime secret and independent buckets passed |
| Spoofed browser identity changes | Did not reset the real platform visitor's quota |
| Actual backup.sh/restore-test.sh | Nonempty source/document/index/vocabulary round-trip passed |
| Linux container SIGTERM | Async finally cleanup observed; exit zero |
| Dependency audits | Full npm audit and installed image Python distribution audit: zero known vulnerabilities |

The frontend test supplies simulated Vercel platform headers locally. It proves
the application boundary, not that a real Vercel deployment is configured.
Backend unit tests additionally cover duplicate headers, IPv6 normalization,
origin scoping, provider/browser secret exclusion and startup configuration.

The API image was built at application revision `b6ed82b`; later changes to the
smoke driver/runbook do not alter that installed application code. The Linux
frontend build includes `a508ec4`; the final driver is `a447db8`. The full native
suite passed at `733ab86`, after fixing a test-only import-time heartbeat clock
that expired under a slower full run. Production heartbeat thresholds were not
changed; each reporting test now freezes its own clock. Invalid secret inputs
are also redacted from startup validation errors. [Sanitized evidence](../../../deploy/reports/oracle-readiness.json)
contains exact suite counts, runtime package versions and image digests.

## Reproduce

From the repository root, with installed native dependencies and a migrated
disposable TEST_DATABASE_URL:

```sh
python scripts/run_all_tests.py --with-build --save
```

On Linux with Docker and permission to clean PostgreSQL-owned temporary files:

```sh
cd frontend
npm ci
NEXT_BUILD_DIR=.next-oracle-readiness npm run build
cd ..
NEXT_BUILD_DIR=.next-oracle-readiness python3 deploy/tests/smoke_stack.py --frontend --output report.json
```

Omit `--frontend` for just the container checks. `--image <already-built-tag>`
reuses a Python image for driver-only changes. The harness does not start crawler
or indexer services. Its SIGTERM probe exercises the common entry-point helper,
not a fully busy crawler under production network load. Cleanup removes only its
unique stack and temporary restore container/volumes.

## Outcome and unverified gates

Adopt the repository topology and trust boundary in ADR-0058. Readiness CI is
configured; GitHub execution and ARM64 build/publication were not dispatched.
Oracle account/VM, real mounted storage, DNS/public certificates, Vercel envs,
real corpus import, scheduled/offsite backups, uptime monitors and representative
sustained load remain explicit operator/release checks. See the
[checklist](../../journal/oracle_deployment_readiness.md).
