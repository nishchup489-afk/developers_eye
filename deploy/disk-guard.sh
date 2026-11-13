#!/bin/sh
# Stops the crawler before the corpus outgrows the VM. Run from cron every 10 minutes:
#   */10 * * * * cd /opt/developers-eye/deploy && ./disk-guard.sh
# It only ever stops the crawler. The API and indexer keep running, and the crawler
# stays stopped until you start it again with: docker compose --profile crawl up -d crawler
# Exit status 1 means a limit was hit, so cron mail or a monitor can report it.
set -eu
cd "$(dirname "$0")"
. "${DEPLOY_ENV_FILE:-./.env}"
min_free_gb=${CRAWL_MIN_FREE_GB:-20}
min_root_free_gb=${CRAWL_MIN_ROOT_FREE_GB:-5}
max_db_gb=${CRAWL_MAX_DB_GB:-25}
max_docs=${CRAWL_MAX_DOCUMENTS:-150000}

free_gb() { df -Pk "$1" | awk 'NR == 2 { print int($4 / 1048576) }'; }
sql() { docker compose exec -T db psql -U developers_eye -d developers_eye -Atqc "$1"; }

reasons=""
data_free=$(free_gb /data)
root_free=$(free_gb /)
[ "$data_free" -ge "$min_free_gb" ] || reasons="$reasons /data has ${data_free} GB free (minimum ${min_free_gb});"
[ "$root_free" -ge "$min_root_free_gb" ] || reasons="$reasons / has ${root_free} GB free (minimum ${min_root_free_gb});"
# Planner estimate for documents: free to read, refreshed by autovacuum/ANALYZE.
if stats=$(sql "SELECT pg_database_size(current_database()) / 1073741824, GREATEST(reltuples, 0)::bigint
               FROM pg_class WHERE relname = 'document'") && [ -n "$stats" ]; then
    db_gb=${stats%%|*}
    docs=${stats#*|}
    [ "$db_gb" -lt "$max_db_gb" ] || reasons="$reasons database is ${db_gb} GB (maximum ${max_db_gb});"
    [ "$docs" -lt "$max_docs" ] || reasons="$reasons about ${docs} documents (maximum ${max_docs});"
else
    db_gb="?" docs="?"
    reasons="$reasons could not read database size;"
fi

if [ -z "$reasons" ]; then
    echo "disk-guard ok: /data ${data_free} GB free, / ${root_free} GB free, database ${db_gb} GB, ~${docs} documents"
    exit 0
fi
message="disk-guard:${reasons}"
if [ -n "$(docker compose --profile crawl ps --status running -q crawler 2>/dev/null)" ]; then
    docker compose --profile crawl stop crawler >/dev/null
    message="$message crawler stopped"
else
    message="$message crawler already stopped"
fi
logger -t developers-eye "$message" 2>/dev/null || true
echo "$message" >&2
exit 1
