# Developer's Eye in production

Live since 2026-11-13. This page covers what is running, where things live and how to
operate it. To build a new server from nothing, follow
[deploy/GO_LIVE.md](deploy/GO_LIVE.md). Every setting, URL and secret location is in
[deploy/.env.production.example](deploy/.env.production.example).

## At a glance

| What | Where |
| --- | --- |
| Frontend | Vercel (root `frontend`, region `iad1`) |
| API | `https://132-145-194-228.sslip.io` (Caddy, Let's Encrypt) |
| Health check | `https://132-145-194-228.sslip.io/health` |
| Server | Oracle A1.Flex 4 OCPU / 24 GB, Ubuntu 24.04 ARM, Ashburn AD-2 |
| SSH | `ssh -i ~/.ssh/oracle-de.key ubuntu@132.145.194.228` |
| Code on server | `/opt/developers-eye` (run compose from `/opt/developers-eye/deploy`) |
| Database | PostgreSQL 18 in Docker, data in `/data/pgdata` (150 GB block volume) |
| Backups | `/data/backups`, nightly, 7 days |
| Secrets | `/opt/developers-eye/deploy/.env` on the server and Vercel settings |

A request travels Browser → Vercel (Next.js) → Caddy on the VM → FastAPI → PostgreSQL.
Caddy refuses anything except `/health` without the shared `EDGE_SHARED_SECRET`, so
only Vercel can search.

### Services

| Service | Job | Starts with `docker compose up -d` |
| --- | --- | --- |
| `db` | PostgreSQL 18 | yes |
| `migrate` | applies Alembic migrations, then exits | yes |
| `api` | FastAPI search API, 1 worker | yes |
| `caddy` | HTTPS, edge-secret check, the only public ports (80/443) | yes |
| `indexer-0` | turns fetched pages into search index rows (batch 100, concurrency 2) | yes |
| `maintenance` | purges old crawl telemetry once a day | yes |
| `crawler` | fetches pages, 2 slots, 2 s per host (~1 page/s) | **no**, needs `--profile crawl` |

All of them restart on their own after a crash or a reboot, including the crawler if
it was running when the VM went down.

### Size limits

- **Per-source caps** (`max_pages` in the database) total about 150K documents
  (`CRAWL_MAX_DOCUMENTS`). On 2026-11-13 the corpus held 112,839 documents (2.2 GB).
- **Disk guard** (cron, every 10 min) stops the crawler if `/data` has under 20 GB
  free, `/` under 5 GB, the database passes 25 GB, or documents reach 150K.

## Open a terminal on the server

From Windows, open **PowerShell** (Start menu, type `PowerShell`) on your PC and run:

```powershell
ssh -i $HOME\.ssh\oracle-de.key ubuntu@132.145.194.228
```

Answer `yes` the first time it asks about the host fingerprint. The prompt changes to
`ubuntu@developers-eye:~$`, which means every command you type now runs on the server.
Then go to the project:

```bash
cd /opt/developers-eye/deploy
```

Type `exit` (or press `Ctrl+D`) to leave the server and return to PowerShell.

**First time on a new PC.** Put the private key at `C:\Users\<you>\.ssh\oracle-de.key`
and make it readable only by you, or SSH refuses it:

```powershell
icacls $HOME\.ssh\oracle-de.key /inheritance:r
icacls $HOME\.ssh\oracle-de.key /grant:r "$($env:USERNAME):(R)"
```

**Shortcut (optional).** Add this to `C:\Users\<you>\.ssh\config` (a plain text file
with no extension) and from then on connect with just `ssh de`:

```text
Host de
    HostName 132.145.194.228
    User ubuntu
    IdentityFile ~/.ssh/oracle-de.key
    ServerAliveInterval 60
```

The same alias works for copying files: `scp de:/data/backups/<file>.dump .`

**From macOS or Linux** use `ssh -i ~/.ssh/oracle-de.key ubuntu@132.145.194.228`, after
`chmod 600 ~/.ssh/oracle-de.key`.

**If SSH does not connect at all** (timeout, key lost): in the Oracle console open
Compute → Instances → the instance → **Console connection** → *Launch Cloud Shell
connection*. This opens a serial terminal in the browser that works without port 22.

## Everyday commands

[Open a terminal on the server](#open-a-terminal-on-the-server) first, then
`cd /opt/developers-eye/deploy`.

### Crawler

| Task | Command |
| --- | --- |
| Start | `docker compose --profile crawl up -d crawler` |
| Stop (indexer keeps going) | `docker compose --profile crawl stop crawler` |
| Is it running? | `docker compose --profile crawl ps crawler` |
| Live log | `docker compose logs -f --tail 50 crawler` (Ctrl+C leaves it running) |
| Restart | `docker compose --profile crawl restart crawler` |

Plain `docker compose up -d` never starts or stops the crawler, so it is safe to run
any time.

### Progress

```sh
# Documents, index backlog and database size
docker compose exec -T db psql -U developers_eye -d developers_eye -c "
SELECT (SELECT count(*) FROM document) AS documents,
       (SELECT count(*) FROM document d LEFT JOIN search_index s ON s.document_id = d.id
         WHERE s.document_id IS NULL OR s.indexed_at < d.updated_at) AS waiting_for_index,
       (SELECT count(*) FROM crawl_attempt WHERE started_at > now() - interval '1 hour') AS fetches_last_hour,
       pg_size_pretty(pg_database_size('developers_eye')) AS db_size"

# Crawl queue by state
docker compose exec -T db psql -U developers_eye -d developers_eye -c \
  "SELECT state, count(*) FROM crawl_target GROUP BY state ORDER BY 2 DESC"

# Disk guard check (also shows free space)
./disk-guard.sh
```

### Whole stack

| Task | Command |
| --- | --- |
| Status | `docker compose --profile crawl ps` |
| Logs | `docker compose logs --tail 100 api` (or `db`, `caddy`, `indexer-0`, `crawler`) |
| Restart the API | `docker compose restart api` |
| Stop everything | `docker compose --profile crawl down` (data stays in `/data`) |
| Start again | `docker compose up -d`, then start the crawler if you want it |
| Memory/CPU | `docker stats --no-stream` |
| Disk | `df -h / /data` and `docker system df` |

### Deploy new code

```sh
cd /opt/developers-eye && git pull
cd deploy && docker compose build && docker compose up -d
# only if the crawler should keep running:
docker compose --profile crawl up -d crawler
```

`migrate` runs before the API and workers start, so schema changes apply on their own.

### Change a setting

Edit `/opt/developers-eye/deploy/.env` with `nano`, then recreate what uses it:
`docker compose up -d --force-recreate api indexer-0 maintenance` (add
`docker compose --profile crawl up -d --force-recreate crawler` if it runs). Vercel
changes need a Redeploy in Vercel.

### Corpus size

```sh
./cap-sources.sh                       # preview caps for CRAWL_MAX_DOCUMENTS
./cap-sources.sh --apply --trim-queue  # shrink caps, park never-fetched pages above them
```

The script only lowers caps. To grow one source (for example after raising the budget):

```sh
docker compose exec -T db psql -U developers_eye -d developers_eye -c \
  "UPDATE source SET config = jsonb_set(config, '{max_pages}', '5000') WHERE slug = 'mdn'"
# un-park pages that --trim-queue parked:
docker compose exec -T db psql -U developers_eye -d developers_eye -c \
  "UPDATE crawl_target SET state = 'queued' WHERE state = 'disabled' AND last_fetched_at IS NULL"
```

Keep `CRAWL_MAX_DOCUMENTS`, `ADMIN_TARGET_DOCUMENTS` and `CRAWL_MAX_DB_GB` in step
when you raise the budget.

### Backups

Cron (`sudo crontab -l`) runs:

```cron
*/10 * * * * cd /opt/developers-eye/deploy && ./disk-guard.sh >/dev/null
15 3 * * * cd /opt/developers-eye/deploy && ./backup.sh
45 4 * * 0 cd /opt/developers-eye/deploy && ./restore-test.sh
```

| Task | Command |
| --- | --- |
| Back up now | `./backup.sh` |
| List backups | `ls -lh /data/backups` |
| Test a restore (temporary container, live data untouched) | `./restore-test.sh` |
| Copy newest backup to the PC | `scp -i $HOME\.ssh\oracle-de.key ubuntu@132.145.194.228:/data/backups/<file>.dump .` (PowerShell) |

Backups stay on the same VM until `BACKUP_REMOTE` is set, so copy one to your PC
now and then.

### Why did the crawler stop?

```sh
journalctl -t developers-eye --since today   # disk-guard decisions
docker compose logs --tail 100 crawler
```

If the guard stopped it, free space or raise the limit in `.env`, then start it again.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Site shows no results / errors | `curl https://132-145-194-228.sslip.io/health`; then `docker compose ps`; then Vercel's `BACKEND_URL` and `EDGE_SHARED_SECRET` |
| `/health` fails | `docker compose logs --tail 50 caddy api` |
| Certificate error | port 80 must be open (Oracle security list and iptables) for renewal |
| `db` restarting, "Permission denied" in its log | `sudo chown 70:70 /data/pgdata && docker compose restart db` |
| `/data` missing after reboot | `sudo mount -a`; check the volume is still attached in Oracle |
| SSH "Permission denied (publickey)" | wrong key path; the key must be `oracle-de.key`, readable only by you |
| Search slow | `docker stats`; slow queries appear in `docker compose logs db` (over 1 s) |

## Costs

Everything above fits Oracle Always Free. Check Billing > Cost analysis once a week at
first. The $1 budget alert only emails you; it does not stop charges. Things that
would cost money: more than 4 OCPU / 24 GB, more than 200 GB of block storage in total,
automatic volume backup policies, or an unattached reserved IP.

## Using a real domain later

Point an A record (for example `api.example.com`) at `132.145.194.228`, set
`SITE_ADDRESS` in `.env`, run `docker compose up -d --force-recreate caddy`, then change
`BACKEND_URL` (and `CRAWLER_REPORT_API_URL` if set) in Vercel and redeploy.
