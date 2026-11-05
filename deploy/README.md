# Deploying Developer's Eye

One server runs everything: PostgreSQL, the API, crawler and indexer workers, the
web app and Caddy for TLS. The target is the Oracle Cloud Always Free ARM shape
(4 OCPU, 24 GB RAM, 200 GB block volume). At about 31 KB per document, 2 million
documents need about 62 GB, which fits.

## First boot

1. Create an Ubuntu ARM VM and attach the block volume. Open ports 80 and 443 in
   the network security list and in the VM firewall.
2. Install Docker and point your domain at the VM.
3. Clone the repository, then:

```bash
cd deploy
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Fill in `.env` before the last step. `migrate` runs Alembic once and every other
service waits for it. Workers register sources and queue start URLs on first start.

## Upgrading an existing database

The new migrations add a generated column to `crawl_target`, which rewrites the
table and locks it while it does. Stop the crawlers first:

```bash
docker compose stop crawler indexer-0 indexer-1
docker compose run --rm migrate
docker compose up -d
```

Vocabulary counts need one rebuild if they were never rebuilt on this database:

```bash
docker compose stop indexer-0 indexer-1
docker compose run --rm indexer-0 python -m indexer.vocabulary_rebuild --once
docker compose up -d
```

## Scaling

| What | How | Limit |
| --- | --- | --- |
| Crawl rate | `docker compose up -d --scale crawler=3` | Hosts in the source list. Each host gets one request every 2 seconds, however many workers run. |
| Index rate | Add `indexer-2` and set every `INDEXER_SHARD_COUNT` to 3 | CPU shared with the database. |
| Connections | Keep `(DB_POOL_SIZE + DB_MAX_OVERFLOW) * processes` under `max_connections` (60) | Beyond that, add PgBouncer. |

Crawl rate is decided by the number of hosts, not workers. 100 active hosts give at
most 50 requests per second.

## Backups

```bash
./backup.sh
./restore-test.sh
```

Schedule `backup.sh` nightly and `restore-test.sh` weekly. Set `BACKUP_REMOTE` for
an offsite copy: a backup on the same disk does not survive losing that disk.

## Health

- Liveness: `docker compose ps` shows health for `db` and `api`.
- Crawl and index progress: the admin dashboard at `/admin`.
- Slow queries: Postgres logs anything over one second (`docker compose logs db`).
