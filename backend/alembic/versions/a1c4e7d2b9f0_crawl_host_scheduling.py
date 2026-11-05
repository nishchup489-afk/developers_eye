"""Add shared per-host politeness state and host-aware frontier indexes.

Revision ID: a1c4e7d2b9f0
Revises: f3b8c1d2e4a5
"""
from alembic import op

revision = "a1c4e7d2b9f0"
down_revision = "f3b8c1d2e4a5"
branch_labels = None
depends_on = None

HOST = r"coalesce(lower(substring(normalized_url from '^[a-z]+://([^/:?#]+)')), '')"


def upgrade():
    op.execute(f"ALTER TABLE crawl_target ADD COLUMN host text GENERATED ALWAYS AS ({HOST}) STORED NOT NULL")
    op.execute("""
        CREATE TABLE crawl_host (
            host text PRIMARY KEY,
            next_allowed_at timestamptz NOT NULL DEFAULT now(),
            backoff_until timestamptz
        ) WITH (fillfactor = 50)
    """)
    op.execute("INSERT INTO crawl_host (host) SELECT DISTINCT host FROM crawl_target")

    # Every writer of crawl_target gets its host registered, however it inserts.
    op.execute("""
        CREATE FUNCTION crawl_target_register_hosts() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO crawl_host (host)
            SELECT DISTINCT host FROM new_targets ORDER BY host
            ON CONFLICT (host) DO NOTHING;
            RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER crawl_target_register_hosts AFTER INSERT ON crawl_target
        REFERENCING NEW TABLE AS new_targets
        FOR EACH STATEMENT EXECUTE FUNCTION crawl_target_register_hosts()
    """)

    op.execute("""
        CREATE INDEX ix_crawl_target_host_due ON crawl_target
        (host, priority DESC, depth, next_fetch_at, id) WHERE state = 'queued'
    """)
    op.execute("CREATE INDEX ix_crawl_target_lease ON crawl_target (lease_until) WHERE state = 'leased'")
    op.execute("CREATE INDEX ix_crawl_attempt_unfinished ON crawl_attempt (crawl_target_id) WHERE finished_at IS NULL")


def downgrade():
    op.execute("DROP INDEX ix_crawl_attempt_unfinished")
    op.execute("DROP INDEX ix_crawl_target_lease")
    op.execute("DROP INDEX ix_crawl_target_host_due")
    op.execute("DROP TRIGGER crawl_target_register_hosts ON crawl_target")
    op.execute("DROP FUNCTION crawl_target_register_hosts()")
    op.execute("DROP TABLE crawl_host")
    op.execute("ALTER TABLE crawl_target DROP COLUMN host")
