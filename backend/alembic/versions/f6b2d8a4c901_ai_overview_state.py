"""Shared, restart-persistent Groq budgets, overview cache and generation leases.

Revision ID: f6b2d8a4c901
Revises: e5a9c3d1f7b2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6b2d8a4c901"
down_revision = "e5a9c3d1f7b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ai_overview_budget", sa.Column("scope", sa.Text(), primary_key=True),
                    sa.Column("state", postgresql.JSONB(), nullable=False))
    op.create_table("ai_overview_cache", sa.Column("key", sa.Text(), primary_key=True),
                    sa.Column("payload", postgresql.JSONB(), nullable=True),
                    sa.Column("expires_at", sa.Float(), nullable=False),
                    sa.Column("lease_until", sa.Float(), nullable=False),
                    sa.Column("lease_owner", sa.Text(), nullable=True))
    op.create_index("ix_ai_overview_cache_expires_at", "ai_overview_cache", ["expires_at"])


def downgrade():
    op.drop_table("ai_overview_cache")
    op.drop_table("ai_overview_budget")
