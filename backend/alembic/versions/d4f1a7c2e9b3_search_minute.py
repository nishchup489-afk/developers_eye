"""Per-minute search outcomes, so the admin dashboard sees every API process.

Revision ID: d4f1a7c2e9b3
Revises: c3e8a5b6d7f1
"""
from alembic import op

revision = "d4f1a7c2e9b3"
down_revision = "c3e8a5b6d7f1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE search_minute (
            minute timestamptz NOT NULL,
            process text NOT NULL,
            successful integer NOT NULL DEFAULT 0,
            invalid integer NOT NULL DEFAULT 0,
            busy integer NOT NULL DEFAULT 0,
            timed_out integer NOT NULL DEFAULT 0,
            database_errors integer NOT NULL DEFAULT 0,
            engine_errors integer NOT NULL DEFAULT 0,
            server_errors integer NOT NULL DEFAULT 0,
            latency_sum_ms bigint NOT NULL DEFAULT 0,
            latency_buckets integer[] NOT NULL,
            PRIMARY KEY (minute, process)
        )
    """)


def downgrade():
    op.execute("DROP TABLE search_minute")
