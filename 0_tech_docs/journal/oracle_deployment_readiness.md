# Oracle Cloud deployment readiness checklist

Repository changes prepared on `codex/oracle-deployment-readiness`, based on
`main` at `996418f`, 2026-11-10. Scope confirmed: **repository readiness only**.
`[x]` means implemented and locally verified; unchecked cloud/operator tasks
were not performed. This is not a go-live approval.

Topology: Vercel/Next.js → HTTPS → Oracle Caddy → FastAPI/PostgreSQL 18,
with one crawler, one indexer and daily telemetry maintenance. Only 80/443 are
published. See [runbook](../../deploy/README.md),
[ADR-0058](../infra/ci-and-containers/ADR-0058-vercel-to-oracle-authenticated-api.md)
and [EXP-0018](../infra/ci-and-containers/EXP-0018-local-oracle-container-readiness.md).

## P0 · Repository topology and storage

- [x] Remove the colocated `web` service; Caddy proxies to `api:8000`.
- [x] Use `SITE_ADDRESS=api.<domain>` in configuration and document DNS/TLS requirements.
- [x] Use one crawler, one indexer (`INDEXER_SHARD_COUNT=1`) and one API process.
- [x] Bind PG18's `/var/lib/postgresql` parent to `/data/pgdata`; refuse automatic host-directory creation.
- [x] Add read-only host preflight for mount presence, real data path, old cluster layouts, secrets and Compose syntax.
- [x] Cap every service's JSON logs at 20 MB × 3.
- [x] Use console-only production crawler logging and WARNING-level SQL.
- [x] Keep database and API ports private; recompute pool maxima (28 steady-state, up to 34 during migration, below 60).
- [x] Use PostgreSQL 18 consistently in Compose and restoration tools to match the local source major.
- [x] Exclude real env files, backups, local reports and alternate Next builds from Docker build context.

## P0 · Vercel-to-API trust

- [x] Add a server-only edge secret, scoped at request time to configured backend origins.
- [x] Refuse sending that credential to provider/browser calls or non-loopback HTTP origins.
- [x] Caddy rejects unauthenticated API calls except `/health`; FastAPI independently enforces the secret.
- [x] Derive visitor identity from Vercel's platform headers; ignore caller-supplied `X-Eye-Client-IP`.
- [x] Validate one normalized IPv4/IPv6 identity only after authentication; reject duplicate/malformed headers.
- [x] Disable Uvicorn's broad forwarded-header trust; search and AI quotas use the validated identity.
- [x] Disable production `/docs`, `/redoc`, and `/openapi.json`.
- [x] Preserve the independent 32+ character admin reporting key; verify edge-only admin requests are denied and both keys succeed.
- [x] Require a valid edge secret at production startup; retain explicit unauthenticated local development mode.
- [ ] Generate/install the actual independent production secrets on Oracle and Vercel.

## P0 · Oracle setup — operator actions outside this request

- [ ] Make the account/PAYG decision after verifying actual quotas, billing and idle-reclaim policy. No upgrade was performed.
- [ ] Verify the 24 GB profile fits the tenancy: current Always Free docs list 2 OCPU/12 GB; paid-tenancy allowances differ. Do not assume this profile is always free.
- [ ] Create the intended A1 ARM Ubuntu VM in the chosen home region/availability domain.
- [ ] Provision/attach/mount the intended block volume at `/data`, configure `/etc/fstab`, and run preflight on that host.
- [ ] Reserve the public IP, checking current address pricing/allowances.
- [ ] Open 80/443 in OCI and host firewall; restrict SSH to the intended client IP; keep 5432/8000 closed.
- [ ] Install Docker Engine/Compose and configure the planned 4 GB swap file.
- [ ] Verify key-only SSH, disabled password login and automatic OS security updates.

## P0 · Domain, TLS and real data

- [ ] Configure the API DNS record to the VM's reserved IP.
- [ ] Verify public HTTPS `/health` with a valid certificate and status `ok`.
- [x] Correct the dump compatibility guidance: PG16 `pg_dump` cannot export a PG18 server; use PG18 dump/restore.
- [x] Document architecture-independent logical transfer, restore-before-migrate ordering, ANALYZE, vocabulary rebuilding and index-version matching.
- [ ] Stop the local workers and create the real seed archive, excluding crawl-event rows.
- [ ] Transfer and restore that archive into a fresh VM database; migrate and ANALYZE.
- [ ] Rebuild vocabulary if required and verify the actual index version matches.
- [ ] Compare snapshot counts and spot-check live searches/admin reports.

## P1 · Backups, monitoring and process lifecycle

- [x] Keep PG18 backups and restoration on the block-volume path; use unique disposable restore containers and remove their anonymous volumes.
- [x] Execute the actual backup/restore scripts against nonempty disposable PG18 data locally.
- [x] Add SIGTERM handling to both worker entry points; test async cleanup and real Linux container termination. Unfinished leases still recover by expiry.
- [x] Give Python services a 45-second Compose stop grace period.
- [ ] Install nightly backup and weekly restore-test schedules on the VM, with visible failure reporting.
- [ ] Configure offsite rclone credentials, measure compressed archive size and set remote lifecycle/retention.
- [ ] Configure external monitors for the API health URL and the Vercel frontend.

## P1 · Vercel project

- [x] Declare Node 24 in package engines and add `iad1` function-region configuration.
- [x] Document root directory, server-only backend/edge envs, optional knowledge-panel/contact settings and safe preview defaults.
- [x] Document admin-off demo defaults and the full external reporting endpoint; remove the invalid internal-Docker web setting.
- [x] Retain Next.js 16.4.5; fresh frontend install/build and full npm audit pass. Recheck upstream advisories before the actual go-live.
- [ ] Set the actual project's Root Directory to `frontend` and verify Node/region settings on Vercel.
- [ ] Install Production backend/edge envs and redeploy; deliberately configure or leave Preview in demo mode.
- [ ] Set the optional Wikipedia contact settings if using that panel.
- [ ] Verify live Vercel → HTTPS Oracle flows and public error states. Enable admin only if desired and separately configured.

## P2 · Repository support and later operations

- [x] Add container-readiness CI with isolated migration, authenticated ingress, real Next.js bridging, backup restoration and SIGTERM checks.
- [x] Add manually dispatched ARM64 build support; SHA-tagged GHCR publication is explicitly opt-in.
- [ ] Execute the ARM64 workflow and verify the image on an actual ARM host; no CI run or image publication was dispatched.
- [x] Refresh the public API reference and `/docs` implementation/status, query bounds, paging and topology descriptions.
- [x] Document single-process rate limits and the connection-budget gate before adding processes.
- [ ] Revalidate capacity, pool totals, shard assignments and representative sustained load before scaling.

## Local verification evidence

- [x] All 12 application suites: **1,390 tests/checks passed, zero skipped**.
- [x] Real local Next.js → Caddy → FastAPI → PG18: live results, runtime edge secret and separate visitor buckets; spoofed identity cannot reset a bucket.
- [x] Local API image built; empty migrations, public health, private API protection, disabled docs and admin-key layering pass.
- [x] Nonempty backup restoration and Linux SIGTERM cleanup pass.
- [x] Full npm audit and audit of the image's complete installed Python distribution list report no known vulnerabilities (unpublished app packages excluded from advisory lookup).

Raw sanitized evidence is linked from EXP-0018. Local Docker testing used HTTP on
a random loopback port and small test buffers; it did not verify Oracle billing,
actual volume mounting, public TLS/DNS, ARM execution, or production load. Current
allowance sources: [Oracle Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm),
[paid-tenancy price list](https://www.oracle.com/cloud/price-list/#pricing-containers).
