# Go live on Oracle Cloud, step by step

This takes you from an empty Oracle account to a public search site: the frontend on
Vercel, and the API, PostgreSQL, a small two-slot crawler and one indexer on one
Oracle A1 VM. Each step ends with a check. Don't move on until it passes.

Background and options are in [README.md](README.md). Why the crawl is small and
opt-in is in [ADR-0059](../0_tech_docs/infra/ci-and-containers/ADR-0059-small-opt-in-production-crawl.md).

Placeholders: `api.example.com` is your API hostname, `<vm-ip>` your reserved IP.

Already live? Day-to-day operations are in [../GO_LIVE.md](../GO_LIVE.md), and every
setting and URL is in [.env.production.example](.env.production.example).

## 0. Before you start (on your PC)

1. Merge the deploy changes to `main` and push, so the VM can clone them.
2. Decide the corpus budget. The default is `CRAWL_MAX_DOCUMENTS=150000` (about
   2 GB of database). You can raise it later.
3. Make a fresh seed dump of your local database with **PostgreSQL 18** tools. A
   PG16 or PG17 `pg_dump` cannot be restored into the VM's PG18. Stop local crawler
   and indexer processes first. From PowerShell, with Docker Desktop running:

   ```powershell
   docker run --rm -it -v ${PWD}:/out postgres:18-alpine pg_dump `
     -h host.docker.internal -U postgres -d developers_eye `
     --format=custom --compress=6 --exclude-table-data=crawl_event --file=/out/seed.dump
   ```

   Check: `seed.dump` exists and is a few hundred MB.

## 1. Oracle account and VM

1. Upgrade the account to **Pay As You Go** (Billing > Upgrade). Always Free usage
   stays at $0, idle free-tier A1 instances are less likely to be reclaimed, and A1
   capacity is easier to get. Keep the $1 budget alert. A budget alert does not
   stop spending, so check Billing after the first week.
2. Compute > Instances > Create:
   - Image: **Ubuntu 24.04 (aarch64)**. Shape: **VM.Standard.A1.Flex**, 4 OCPU / 24 GB.
     If your tenancy only allows 2 OCPU / 12 GB, use that and see step 5.4.
   - Networking: your existing VCN and public subnet, with a public IP.
   - Add your SSH public key. Boot volume: 50 GB.
   - "Out of host capacity" means try again later or another availability domain.
3. Networking > Reserved public IPs: reserve one and attach it to the VM's VNIC.
4. Storage > Block Volumes: create ~150 GB in the same availability domain and
   attach it to the VM (paravirtualized). Boot plus block must stay within 200 GB.
5. VCN security list: allow TCP 80 and 443 from `0.0.0.0/0`. Limit TCP 22 to your
   home IP. Never open 5432 or 8000.

Check: `ssh ubuntu@<vm-ip>` works.

## 2. Prepare the VM

Run these on the VM.

1. Updates and automatic security patches:

   ```sh
   sudo apt update && sudo apt -y upgrade
   sudo apt -y install unattended-upgrades git
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```

2. Host firewall. Oracle's Ubuntu images reject everything except SSH:

   ```sh
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```

3. Mount the block volume at `/data`. Find it with `lsblk` (usually `sdb`, about
   150G, no partitions). **Formatting erases it, so check the size first.**

   ```sh
   lsblk
   sudo mkfs.ext4 -L devdata /dev/sdb          # only on the new, empty volume
   sudo mkdir -p /data
   echo "UUID=$(sudo blkid -s UUID -o value /dev/sdb) /data ext4 defaults,_netdev,nofail 0 2" | sudo tee -a /etc/fstab
   sudo mount -a && mountpoint /data
   sudo install -d -m 0700 -o 70 -g 70 /data/pgdata   # postgres:18-alpine runs as uid 70
   sudo install -d -m 0700 /data/backups
   sudo install -d -o ubuntu -g ubuntu /data/upload
   ```

4. A 4 GB swap file as a safety net:

   ```sh
   sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

5. Docker Engine and the Compose plugin:

   ```sh
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu && newgrp docker
   ```

6. SSH: in `/etc/ssh/sshd_config` make sure `PasswordAuthentication no`, then
   `sudo systemctl restart ssh`.

Check: `mountpoint /data`, `docker compose version`, and after a `sudo reboot`,
`/data` is still mounted.

## 3. DNS

Create an **A record** `api.example.com` pointing at `<vm-ip>`. No domain? A free
DuckDNS name works, and so does `<vm-ip-with-dashes>.sslip.io`.

Check: `dig +short api.example.com` prints `<vm-ip>`.

## 4. Code and secrets

```sh
sudo mkdir -p /opt/developers-eye && sudo chown ubuntu: /opt/developers-eye
git clone https://github.com/nishchup489-afk/developers_eye.git /opt/developers-eye
cd /opt/developers-eye/deploy
cp .env.example .env && chmod 600 .env
openssl rand -hex 32   # run three times: one value per secret below
nano .env
```

In `.env` set:

- `SITE_ADDRESS=api.example.com` (no `https://`)
- `POSTGRES_PASSWORD`, `EDGE_SHARED_SECRET`, `CRAWLER_REPORT_API_KEY`: three different values
- `CRAWL_MAX_DOCUMENTS` and `ADMIN_TARGET_DOCUMENTS`: your budget (both 150000 by default)
- On a 12 GB VM only: uncomment `POSTGRES_CONFIG=postgresql-12gb.conf` and `POSTGRES_SHM_SIZE=3gb`
- Optional: `GROQ_API_KEY` for AI overviews, or `AI_OVERVIEW=false`

Save a copy of the three secrets in your password manager. Never commit `.env`.

```sh
./preflight.sh
docker compose build
```

Check: preflight prints "Preflight passed" and the build finishes (10-20 minutes on ARM).

## 5. Load your corpus

1. Copy the dump from your PC: `scp seed.dump ubuntu@<vm-ip>:/data/upload/seed.dump`
2. Restore it into the new, empty database **before** anything else starts:

   ```sh
   cd /opt/developers-eye/deploy
   docker compose up -d db
   docker compose cp /data/upload/seed.dump db:/tmp/seed.dump
   docker compose exec -T db pg_restore -U developers_eye -d developers_eye \
     --jobs=4 --no-owner --no-privileges --exit-on-error /tmp/seed.dump
   docker compose run --rm migrate
   docker compose exec -T db psql -U developers_eye -d developers_eye -c ANALYZE
   docker compose exec db rm /tmp/seed.dump
   ```

3. Fit the restored sources to your budget. Preview first, then apply:

   ```sh
   ./cap-sources.sh
   ./cap-sources.sh --apply --trim-queue
   ```

4. If `INDEXER_INDEX_VERSION` differs from your local worker, or search finds
   nothing later, rebuild the vocabulary once:
   `docker compose run --rm indexer-0 python -m indexer.vocabulary_rebuild --once`

Check: document and source counts match your local database:
`docker compose exec db psql -U developers_eye -d developers_eye -c "SELECT COUNT(*) FROM document"`

No dump? Skip 5.1-5.2 and seed an empty database instead:
`docker compose run --rm crawler python -m crawler.seed.seed`, then step 5.3.

## 6. Start the site (no crawler yet)

```sh
docker compose up -d
docker compose ps
```

This starts `db`, `api`, `indexer-0`, `maintenance` and `caddy`. The crawler stays off.

Check, from your PC:

- `curl https://api.example.com/health` returns `{"status":"ok"...}` with no certificate warning.
- `curl -i https://api.example.com/search?q=python` returns **403** (no edge secret).

If TLS fails, read `docker compose logs caddy`. Usually DNS or port 80 isn't reachable.

## 7. Vercel frontend

In the Vercel project: Root Directory `frontend`, Node 24. Under Settings >
Environment Variables (Production):

| Variable | Value |
| --- | --- |
| `BACKEND_URL` | `https://api.example.com` |
| `EDGE_SHARED_SECRET` | the same value as on the VM |
| `WIKIPEDIA_USER_AGENT` | optional, a real contact |

Redeploy.

Check: on the Vercel URL, search works, paging works, and switching sources works.

## 8. Backups, guard and monitoring

```sh
sudo crontab -e
```

```cron
*/10 * * * * cd /opt/developers-eye/deploy && ./disk-guard.sh >/dev/null
15 3 * * * cd /opt/developers-eye/deploy && ./backup.sh
45 4 * * 0 cd /opt/developers-eye/deploy && ./restore-test.sh
```

- Run `./disk-guard.sh` and `./backup.sh` once by hand.
- Optional offsite copies: set up an rclone remote (for example Oracle Object
  Storage) and set `BACKUP_REMOTE` in `.env`.
- Add free uptime checks (for example UptimeRobot) on `https://api.example.com/health`
  and on the Vercel URL.

Check: `./disk-guard.sh` prints `disk-guard ok`, and a file appears in `/data/backups`.

## 9. Turn on the crawler

Only after steps 5-8 pass:

```sh
docker compose --profile crawl up -d crawler
docker compose logs -f --tail 50 crawler
```

Expect about one page a second. Watch `/data` with `df -h /data`, and watch the
admin dashboard if you enabled it.

Pause it any time with `docker compose --profile crawl stop crawler`. The indexer
keeps processing what was fetched. If the guard stops it, read the reason in
`journalctl -t developers-eye`, free space or raise the limit, then start it again.

## Day-2 commands

| Task | Command |
| --- | --- |
| Status | `docker compose --profile crawl ps` |
| Logs | `docker compose logs --tail 100 api` (or `indexer-0`, `crawler`) |
| Update code | `git pull && docker compose build && docker compose up -d` (add `--profile crawl` if the crawler should keep running) |
| Stop everything | `docker compose --profile crawl down` |
| Raise the budget | edit `CRAWL_MAX_DOCUMENTS`, then `./cap-sources.sh --apply` (caps only go down, so to raise them, update `source.config` by hand) |
| Disk use | `df -h /data /` and `docker system df` |

## Not verified yet

These files were checked with `docker compose config` and the scripts against a
test PostgreSQL. Nothing here has run on the real VM, so treat the first run of
each step as the test.
