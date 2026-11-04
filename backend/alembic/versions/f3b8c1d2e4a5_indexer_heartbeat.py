"""Add indexer worker heartbeats for admin liveness and problem checks.

Revision ID: f3b8c1d2e4a5
Revises: 9a71c3fb20d4
"""
from alembic import op
import sqlalchemy as sa

revision = "f3b8c1d2e4a5"
down_revision = "9a71c3fb20d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("indexer_worker",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_batch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("indexed_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_total", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade():
    op.drop_table("indexer_worker")
