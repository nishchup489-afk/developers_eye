# Vercel frontend and Oracle API deployment

First deployment? Follow [GO_LIVE.md](GO_LIVE.md) step by step. This page explains the pieces.

Vercel runs the frontend (`frontend/`, Node 24, `iad1`). Its server routes call
the Oracle VM's HTTPS API. Caddy terminates TLS and authenticates that hop;
FastAPI independently checks the credential before trusting a visitor IP.
The VM runs PostgreSQL 18, one API process, one two-slot crawler (opt-in), one indexer and daily
telemetry maintenance. Only Caddy publishes ports 80/443. Browser requests stay
on the frontend origin, so this topology needs no API CORS configuration.

This is a **4 OCPU / 24 GB** profile. Verify your actual tenancy allowance before
provisioning: Oracle currently lists 2 OCPU/12 GB for Always Free tenancies and,
separately, 3,000 OCPU hours/18,000 GB hours monthly for paid tenancies, shared
across A1 resources. A budget alert is not a spending cap. See
[Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
and [paid-tenancy allowances](https://www.oracle.com/cloud/price-list/#pricing-containers).
The repository does not upgrade an account or guarantee a zero bill.

## Host and secrets

Create the ARM Ubuntu VM in the chosen home region. Mount the intended block
volume at `/data`; verify its device/UUID before formatting anything. Configure
`/etc/fstab` using the actual UUID and network-volume mount options. `nofail`
does not prove the disk is mounted. Install Docker Engine and Compose, keep SSH
key-only and limited to your IP, and enable OS security updates. Open 80/443 in
both OCI rules and the host firewall; leave 5432/8000 private. Reserve the public
IP and point the API hostname at it. Account, firewall, disk, swap and DNS setup
remain operator actions.

After cloning to `/opt/developers-eye`:

```sh
cd /opt/developers-eye/deploy
mountpoint /data
sudo install -d -m 0700 -o 70 -g 70 /data/pgdata   # postgres:18-alpine runs as uid 70
sudo install -d -m 0700 /data/backups
sudo install -d -o ubuntu -g ubuntu /data/upload
cp .env.example .env
chmod 600 .env
```

Set the real `SITE_ADDRESS=api.<domain>` (no scheme), the data path, and three
independent secrets: `POSTGRES_PASSWORD`, `EDGE_SHARED_SECRET`, and
`CRAWLER_REPORT_API_KEY`. Generate each with `openssl rand -hex 32`. Use a hex
database password so the configured URL remains valid. Keep `.env`
shell-compatible because the host scripts source it. Never commit it.

```sh
./preflight.sh
docker compose build
```

Preflight checks secret lengths, hostname, the `/data` mount, resolved data path,
old cluster layouts and Compose configuration without printing secret values.
Compose refuses to create a missing data directory. PG18 mounts
`/var/lib/postgresql` and stores data under `18/docker`
([official layout](https://hub.docker.com/_/postgres)). Do not reuse a PG16/17
data directory. Choose one database setup path before starting workers.

## Empty database or local seed

For a new empty corpus, `docker compose up -d` runs Alembic before the API,
indexer and maintenance. It does not start the crawler, which sits in the `crawl`
profile. Seed sources, cap them, then start crawling on purpose:

```sh
docker compose run --rm crawler python -m crawler.seed.seed
./cap-sources.sh            # preview
./cap-sources.sh --apply
docker compose --profile crawl up -d crawler
```

For a local seed, check `SHOW server_version` and `pg_dump --version`. A PG16
client **cannot** dump a PG18 server. Use PG18 tools and restore into PG18;
logical archives are portable from x86 to ARM. See
[PostgreSQL compatibility](https://www.postgresql.org/docs/18/app-pgdump.html).
Stop local crawler/indexer processes for a stable comparison. Use a password
prompt or `.pgpass`, not a password in the command:

```sh
pg_dump -h localhost -U postgres -d developers_eye --format=custom --compress=6 \
  --exclude-table-data=crawl_event --file=seed.dump
scp seed.dump ubuntu@<vm-host>:/data/upload/seed.dump
```

Upload the archive to `/data/upload`. Restore into a **new empty database
before migrations or workers**, never over an existing application database:

```sh
cd /opt/developers-eye/deploy
docker compose up -d db
docker compose cp /data/upload/seed.dump db:/tmp/seed.dump
docker compose exec -T db pg_restore -U developers_eye -d developers_eye \
  --jobs=4 --no-owner --no-privileges --exit-on-error /tmp/seed.dump
docker compose run --rm migrate
docker compose exec -T db psql -U developers_eye -d developers_eye -c ANALYZE
```

Match `INDEXER_INDEX_VERSION` to the local worker. If vocabulary needs a rebuild,
keep the indexer stopped and run:

```sh
docker compose run --rm indexer-0 python -m indexer.vocabulary_rebuild --once
docker compose up -d
```

A restored database brings its own source caps. Fit them to this VM before any
crawl with `./cap-sources.sh` and then `./cap-sources.sh --apply`.

Compare source/document/index counts with the local snapshot, run known searches
through Vercel and inspect authorized admin reports. Local smoke tests do not
claim to have transferred your corpus to the VM.

## Crawl size and disk

The crawler runs one process with two slots and a 2 s gap per host, about one page
a second. That sets the pace, not the size. Two limits bound the size:

- **Per-source caps.** A source's `max_pages` (in `source.config`, default 10,000)
  caps how many URLs it can ever queue; recrawls update existing documents. The
  seeds add up to about 700K. `./cap-sources.sh --apply` scales every enabled
  source down to fit `CRAWL_MAX_DOCUMENTS`. Add `--trim-queue` to park never-fetched
  pages above the new caps (state `disabled`, nothing deleted). Caps live in the
  database, so rerun it after any restore or reseed.
- **Disk guard.** `./disk-guard.sh` stops the crawler when `/data` free space drops
  below `CRAWL_MIN_FREE_GB`, `/` below `CRAWL_MIN_ROOT_FREE_GB`, the database
  passes `CRAWL_MAX_DB_GB`, or the document estimate reaches `CRAWL_MAX_DOCUMENTS`.
  Schedule it every 10 minutes. It never restarts the crawler.

`ADMIN_TARGET_DOCUMENTS` and `ADMIN_DB_BUDGET_GB` only drive dashboard progress and
warnings. `crawl_attempt` still gains one row per fetch and is not purged; the
guard's database limit is what catches it. Use `docker compose --profile crawl
stop crawler` to pause crawling and `docker compose --profile crawl down` to stop
everything. See [ADR-0059](../0_tech_docs/infra/ci-and-containers/ADR-0059-small-opt-in-production-crawl.md).

## Vercel settings and API trust

Set Root Directory to `frontend`, Node to 24, then configure Production variables
and redeploy. `frontend/vercel.json` selects `iad1`, near Ashburn.

| Server-only variable | Value |
| --- | --- |
| `BACKEND_URL` | `https://api.<domain>` |
| `EDGE_SHARED_SECRET` | Same edge credential as the VM |
| `KNOWLEDGE_PANEL` | Optional on/off |
| `WIKIPEDIA_USER_AGENT` | Optional real operator contact |

Leave admin/OAuth/reporting credentials unset for a public demo. To enable admin
later, configure its allowlist and session/OAuth settings, reporting key, and the
**full** URL `CRAWLER_REPORT_API_URL=https://api.<domain>/admin/crawler/report`.
The internal Docker hostname `http://api:8000` is unreachable from Vercel.
Preview can stay in labeled demo mode instead of sharing production credentials.
Keep Groq keys on the backend; never use `NEXT_PUBLIC_` for any secret.

Axios attaches the edge credential only to configured backend origins, never
GitHub/Wikipedia. Next derives visitor identity from
[Vercel's overwritten headers](https://vercel.com/docs/headers/request-headers),
ignoring caller-supplied `X-Eye-Client-IP`. Caddy rejects missing/wrong credentials
except on `/health`. FastAPI validates the credential again and normalizes a
single IP for search/AI quotas. Uvicorn proxy-header trust is disabled. Admin
endpoints still require their independent service key; production docs are off.

## Live checks still required

- `https://api.<domain>/health` must return status `ok` with a valid certificate.
  This is liveness, not proof of database/search/frontend readiness.
- Direct unauthenticated `/search` and `/health/db` must return 403.
- The Vercel UI must perform live search, paging, source/mode changes and correct
  rate limiting for separate visitors. Missing edge configuration fails closed.
- Verify import counts, migration head and actual crawl/index progress.

These remain operator checks until performed. See the
[readiness checklist](../0_tech_docs/journal/oracle_deployment_readiness.md).

## Backups and shutdown

`./backup.sh` writes PG18 custom archives under `/data/backups`, skips
`crawl_event` data and keeps seven days. `./restore-test.sh [archive]` restores
into a unique temporary PG18 container, checks nonempty core tables against live
counts and executes a search query. Startup waiting is bounded. This is not an
exact snapshot-count comparison while the live database changes.

Schedule nightly backups and weekly restore testing on the host. Example root
crontab commands for this checkout:

```cron
*/10 * * * * cd /opt/developers-eye/deploy && ./disk-guard.sh >/dev/null
15 3 * * * cd /opt/developers-eye/deploy && ./backup.sh
45 4 * * 0 cd /opt/developers-eye/deploy && ./restore-test.sh
```

Configure cron output delivery/monitoring so failures are visible. Set
`BACKUP_REMOTE` to a dedicated rclone offsite path, with credentials outside Git.
Measure compressed dump size against the allowance first. Local pruning does
**not** prune remote copies; configure remote lifecycle/retention separately.
Add external uptime monitors for both the API and Vercel URL. No schedules,
remote credentials or external monitors are installed by this repository.

Compose caps each service's JSON logs at 20 MB × 3. The production crawler logs
to console and sets SQL to WARNING. SIGTERM cancels active worker tasks, permits
monitor/session/engine cleanup, and leaves unfinished crawl leases to recovery.
It does not finish every in-flight crawl. Compose allows 45 seconds before
SIGKILL; abrupt crashes still rely on fencing, rollback and lease expiry.

## Local validation and later scaling

Run `python3 deploy/tests/smoke_stack.py --output report.json` with Docker access
and permission to clean PostgreSQL-owned temporary files (CI uses sudo).
It builds the API image and uses a unique local PG18/API/Caddy stack to verify
empty migrations, auth rejection, spoof resistance, separate rate buckets,
admin-key layering and disabled docs. It never reads real env files or starts a
crawler. Local HTTP validation does not establish public TLS, OCI or ARM runtime.

CI runs that smoke test for deployment changes. Manual dispatch of the same
workflow also builds `linux/arm64`; GHCR publication is opt-in through `publish`.
No workflow or image publication was dispatched here. Vercel builds the frontend
separately; backend and worker services use the shared Python image.

Steady-state pool maxima total 22: API 10 (8 + 2) plus crawler, indexer and
maintenance 4 each (2 + 2). Migration adds at most 4, leaving reserve below
PostgreSQL's 60 for backup/admin connections. Recompute before scaling. Indexer shards must be coordinated, and
crawlers must keep shared host pacing. On a 12 GB VM, set `POSTGRES_CONFIG=postgresql-12gb.conf`
and `POSTGRES_SHM_SIZE=3gb` in `.env` to use the smaller database tuning.
