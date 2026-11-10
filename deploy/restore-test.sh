#!/bin/sh
# Prove a backup restores: load it into a throwaway Postgres and compare row counts
# with the live database. Run weekly. An untested backup is not a backup.
#   ./restore-test.sh [backups/some.dump]
set -eu
cd "$(dirname "$0")"
. "${DEPLOY_ENV_FILE:-./.env}"
file=${1:-$(ls -t "${BACKUP_DIR:-/data/backups}"/*.dump | head -n 1)}
[ -r "$file" ] || { echo "No readable backup found" >&2; exit 1; }
name=developers-eye-restore-test-$(date +%s)-$$
password=$(openssl rand -hex 16)

trap 'docker rm -fv "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" -e POSTGRES_PASSWORD="$password" postgres:18-alpine >/dev/null
ready=0
for attempt in $(seq 1 60); do
    if docker exec "$name" pg_isready -U postgres >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
done
[ "$ready" -eq 1 ] || { echo "Restore-test database did not become ready" >&2; exit 1; }

docker exec "$name" createdb -U postgres developers_eye
docker exec -i "$name" pg_restore -U postgres -d developers_eye --no-owner --exit-on-error < "$file"

count() { docker exec "$name" psql -U postgres -d developers_eye -tAc "SELECT count(*) FROM $1"; }
live() { docker compose exec -T db psql -U developers_eye -d developers_eye -tAc "SELECT count(*) FROM $1"; }

failed=0
for table in source document search_index search_terms crawl_target; do
    restored=$(count "$table")
    current=$(live "$table")
    echo "$table: restored=$restored live=$current"
    # The live database keeps growing, so a backup may be behind it, but never empty.
    if [ "$restored" -eq 0 ] && [ "$current" -gt 0 ]; then failed=1; fi
done
docker exec "$name" psql -U postgres -d developers_eye -tAc \
    "SELECT document_id FROM search_index WHERE search_vector @@ to_tsquery('english', 'python') LIMIT 1" >/dev/null
[ "$failed" -eq 0 ] && echo "Restore test passed: $file"
exit "$failed"
