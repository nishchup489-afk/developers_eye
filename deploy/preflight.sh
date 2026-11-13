#!/bin/sh
# Read-only host checks. Run on the Oracle VM before docker compose up.
set -eu
cd "$(dirname "$0")"
[ -f .env ] || { echo "Copy .env.example to .env and configure it first" >&2; exit 1; }
. ./.env
for name in POSTGRES_PASSWORD EDGE_SHARED_SECRET CRAWLER_REPORT_API_KEY; do
    # Values sourced above need not have been exported.
    case "$name" in
        POSTGRES_PASSWORD) value=${POSTGRES_PASSWORD:-} ;;
        EDGE_SHARED_SECRET) value=${EDGE_SHARED_SECRET:-} ;;
        CRAWLER_REPORT_API_KEY) value=${CRAWLER_REPORT_API_KEY:-} ;;
    esac
    [ "${#value}" -ge 32 ] || { echo "$name must contain at least 32 characters" >&2; exit 1; }
done
case "$POSTGRES_PASSWORD" in *[!a-fA-F0-9]*) echo "Use a hex POSTGRES_PASSWORD so the database URL is valid" >&2; exit 1 ;; esac
case "${SITE_ADDRESS:-}" in ""|*example.com*|*/*|*:*) echo "Set SITE_ADDRESS to your API hostname, without scheme/port/path" >&2; exit 1 ;; esac
mountpoint -q /data || { echo "/data is not mounted; refusing to put database files on the boot disk" >&2; exit 1; }
path=$(realpath -e "${PGDATA_HOST_PATH:-/data/pgdata}")
case "$path" in /data/*) ;; *) echo "PGDATA_HOST_PATH must resolve inside mounted /data" >&2; exit 1 ;; esac
[ "$(stat -c %u "$path")" = 70 ] || { echo "$path must be owned by uid 70 (postgres in postgres:18-alpine): sudo chown 70:70 $path" >&2; exit 1; }
if [ -f "$path/PG_VERSION" ] || [ -d "$path/16" ] || [ -d "$path/17" ]; then
    echo "An older PostgreSQL data layout exists; restore a compatible logical dump into a new PG18 directory" >&2
    exit 1
fi
docker compose config --quiet
docker info --format 'Docker architecture: {{.Architecture}}'
df -h /data
echo "Preflight passed. This does not verify DNS, TLS, billing, backups, or the deployed API."
