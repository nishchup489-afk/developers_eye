#!/bin/sh
# Nightly database backup. Cron: 15 3 * * * cd /opt/developers-eye/deploy && ./backup.sh
# crawl_event data is left out: it is telemetry and is the fastest-growing table.
set -eu
cd "$(dirname "$0")"
. "${DEPLOY_ENV_FILE:-./.env}"
backups=${BACKUP_DIR:-/data/backups}
keep_days=${BACKUP_KEEP_DAYS:-7}
mkdir -p "$backups"
file="$backups/developers_eye-$(date -u +%Y%m%dT%H%M%SZ).dump"

docker compose exec -T db pg_dump -U developers_eye -d developers_eye \
    --format=custom --compress=6 --exclude-table-data=crawl_event > "$file.partial"
mv "$file.partial" "$file"

if [ -n "${BACKUP_REMOTE:-}" ]; then
    rclone copy "$file" "$BACKUP_REMOTE"
fi
find "$backups" -name '*.dump' -mtime "+$keep_days" -delete
echo "Backup written: $file ($(du -h "$file" | cut -f1))"
