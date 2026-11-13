#!/bin/sh
# Shrink every enabled source's max_pages so the whole corpus fits a document budget.
#
#   ./cap-sources.sh                     preview, changes nothing
#   ./cap-sources.sh --apply             write the new caps
#   ./cap-sources.sh --apply --trim-queue  also park never-fetched pages above each cap
#
# The budget is CRAWL_MAX_DOCUMENTS from .env (default 150000). Caps scale down in
# proportion to their current size, never up, with a floor of 20 pages per source.
# max_pages lives in the database (source.config), so run this after every restore
# or reseed. Seeding never overwrites an existing source, so the caps stick.
# --trim-queue sets parked targets to state 'disabled'; nothing is deleted. Undo with
#   UPDATE crawl_target SET state = 'queued' WHERE state = 'disabled' AND last_fetched_at IS NULL;
set -eu
cd "$(dirname "$0")"
. "${DEPLOY_ENV_FILE:-./.env}"
apply=false
trim=false
for arg in "$@"; do
    case "$arg" in
        --apply) apply=true ;;
        --trim-queue) trim=true ;;
        *) echo "usage: $0 [--apply] [--trim-queue]" >&2; exit 2 ;;
    esac
done
target=${CRAWL_MAX_DOCUMENTS:-150000}
case "$target" in ''|*[!0-9]*) echo "CRAWL_MAX_DOCUMENTS must be a whole number" >&2; exit 1 ;; esac
[ "$trim" = false ] || [ "$apply" = true ] || { echo "--trim-queue needs --apply" >&2; exit 2; }

psql() {
    docker compose exec -T db psql -U developers_eye -d developers_eye -v ON_ERROR_STOP=1 \
        -v target="$target" -v apply="$apply" -v trim="$trim" "$@"
}

psql <<'SQL'
\pset footer off
CREATE TEMP TABLE planned_cap AS
WITH current_caps AS (
    SELECT id, slug, COALESCE((config->>'max_pages')::int, 10000) AS cap
    FROM source WHERE is_enabled
), totals AS (
    SELECT SUM(cap)::numeric AS total FROM current_caps
)
SELECT c.id, c.slug, c.cap AS old_cap,
       LEAST(c.cap, GREATEST(20, FLOOR(c.cap * LEAST(1, :target / NULLIF(t.total, 0)))::int)) AS new_cap
FROM current_caps c CROSS JOIN totals t;

\echo 'Document budget (CRAWL_MAX_DOCUMENTS):' :target
SELECT COUNT(*) AS enabled_sources, SUM(old_cap) AS current_total_cap, SUM(new_cap) AS planned_total_cap,
       (SELECT COUNT(*) FROM document) AS documents_now
FROM planned_cap;
SELECT slug, old_cap, new_cap FROM planned_cap ORDER BY old_cap DESC LIMIT 15;

\if :apply
BEGIN;
UPDATE source s
SET config = jsonb_set(s.config, '{max_pages}', to_jsonb(p.new_cap))
FROM planned_cap p
WHERE s.id = p.id AND p.new_cap < p.old_cap;
\if :trim
WITH ranked AS (
    SELECT ct.id, p.new_cap,
           ROW_NUMBER() OVER (PARTITION BY ct.source_id
                              ORDER BY ct.last_fetched_at IS NULL, ct.priority DESC, ct.depth, ct.id) AS rank
    FROM crawl_target ct JOIN planned_cap p ON p.id = ct.source_id
)
UPDATE crawl_target ct
SET state = 'disabled'
FROM ranked r
WHERE ct.id = r.id AND r.rank > r.new_cap
  AND ct.state = 'queued' AND ct.last_fetched_at IS NULL AND ct.kind = 'page';
\endif
COMMIT;
\echo 'Caps applied.'
\else
\echo 'Preview only. Re-run with --apply to write these caps.'
\endif
SQL
