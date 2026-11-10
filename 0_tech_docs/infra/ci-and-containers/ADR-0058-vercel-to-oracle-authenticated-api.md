---
id: ADR-0058
title: Deploy Vercel behind a scoped authenticated API hop to Oracle
status: accepted
date: 2026-11-10
area: infra
feature: ci-and-containers
code: [deploy/docker-compose.yml, deploy/Caddyfile, backend/src/backend/api/edge_trust.py, frontend/lib/axios.js]
related: [ADR-0039, ADR-0041, ADR-0046, ADR-0056, INC-0042, EXP-0018]
---

# ADR-0058: Vercel frontend, authenticated Oracle API

## Decision

Vercel hosts the Next.js frontend in `iad1`. Caddy on the Oracle VM fronts
PostgreSQL 18, one FastAPI process, one crawler, one indexer and maintenance.
Only Caddy publishes ports. Browser requests stay on the Vercel origin.

Use an independent 32+ character server-only `EDGE_SHARED_SECRET` for this hop.
The Axios request interceptor attaches it only to the configured backend/report
origins. It is never a client default header and must not accompany GitHub,
Wikipedia, browser-side calls or redirects. Outside loopback, authenticated
backend origins require HTTPS. Resolve the secret at request time.

Caddy rejects requests without the credential except `/health`. FastAPI also
checks it with constant-time comparison before accepting a single syntactically
valid `X-Eye-Client-IP`. Next derives that header from Vercel's overwritten
platform forwarding headers; it never preserves a caller-supplied identity.
FastAPI replaces the request client identity for search/overview quotas.
Uvicorn's generic proxy-header trust is disabled. Duplicate credentials/identity
headers and malformed IPs fail closed. Production startup requires the secret.
Admin endpoints retain the separate reporting service key. API docs are off.

## Storage and operational boundaries

Use PG18 to match the existing local source database; an older dump client
cannot export a newer server. Bind the mounted block-volume directory at the
PG18 image's `/var/lib/postgresql` parent. Never reuse a PG16 data directory.
Preflight verifies `/data` is mounted and resolves the configured directory;
Compose does not create a missing host directory. Run preflight before startup.

All services have bounded Docker logs; production crawler logging is console-only
with SQL WARNING. Workers handle SIGTERM through cooperative cancellation and
existing cleanup; unfinished leases recover by expiry. A second SIGTERM does not
interrupt cleanup. Docker still has a 45-second final kill bound.

Normal pool maxima total 28, with at most 6 more for migration. Retain reserve
below 60 for administrative/backup work. More processes require a new budget.

## Alternatives and limits

- A secret as an Axios default header would leak it to third-party calls; rejected.
- Trusting arbitrary XFF or raw browser identity would permit spoofing; rejected.
- Trusting only Caddy would leave accidental direct API exposure unguarded; add
  the application check too. Internal-only service ports remain necessary.
- Keep PostgreSQL 16 and use its dump client against local PG18: unsupported.
  A fresh PG18 logical restore is the selected first-deployment path.
- This profile assumes 24 GB. It is not unchanged tuning for a 12 GB free VM.

The shared secret authenticates the hop; it is not per-user authentication.
Per-process search rate limits remain suitable only for the selected one-process
demo topology. This decision does not claim live cloud, TLS, ARM runtime,
backup scheduling, external monitors or a human relevance gate were verified.

## Verification

[EXP-0018](EXP-0018-local-oracle-container-readiness.md) records local unit,
full-suite, Docker ingress, nonempty backup restoration and SIGTERM checks.
The smoke harness namespaces containers, volumes, networks and temporary data;
it uses generated credentials and never starts public crawls. Optional real
Next.js testing verifies runtime secret injection and independent visitor limits.
CI includes the smoke gate and a manually dispatched ARM64 build; publishing
to GHCR is a separate opt-in action, not an automatic production rollout.

## Rules for future changes

- Never set the edge credential in Axios defaults or a `NEXT_PUBLIC_` variable.
- Keep runtime origin scoping, duplicate-header rejection and real rate-limit
  identity tests when changing ingress or transports.
- Preserve public liveness without treating it as database/search readiness.
- Revalidate database major/layout, mount presence, pool and memory budgets.
