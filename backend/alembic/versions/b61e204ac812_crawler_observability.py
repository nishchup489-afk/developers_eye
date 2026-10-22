"""Add crawler stage history, attempt measurements and worker heartbeats.

Revision ID: b61e204ac812
Revises: 715c87a9c745
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b61e204ac812"
down_revision = "715c87a9c745"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("crawl_attempt", sa.Column("telemetry", postgresql.JSONB(), nullable=True))
    op.create_index("ix_crawl_attempt_started_at", "crawl_attempt", ["started_at"])
    op.create_index("ix_document_last_seen_at", "document", ["last_seen_at"])
    op.create_index("ix_document_content_hash", "document", ["content_hash"])
    op.create_table("crawl_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("attempt_id", sa.BigInteger(), sa.ForeignKey("crawl_attempt.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False))
    op.create_index("ix_crawl_event_attempt_id_id", "crawl_event", ["attempt_id", "id"])
    op.create_index("ix_crawl_event_created_at", "crawl_event", ["created_at"])
    op.create_table("crawl_worker",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("active_targets", postgresql.JSONB(), nullable=False))


def downgrade():
    op.drop_table("crawl_worker")
    op.drop_table("crawl_event")
    op.drop_index("ix_document_last_seen_at", table_name="document")
    op.drop_index("ix_document_content_hash", table_name="document")
    op.drop_index("ix_crawl_attempt_started_at", table_name="crawl_attempt")
    op.drop_column("crawl_attempt", "telemetry")
