"""Index document.last_crawl_target_id, which a 404 or 410 looks documents up by.

Without it each such response scans the whole document table inside the crawl
finalize transaction. CONCURRENTLY keeps crawler writes running during the build.

Revision ID: e5a9c3d1f7b2
Revises: d4f1a7c2e9b3
"""
from alembic import op

revision = "e5a9c3d1f7b2"
down_revision = "d4f1a7c2e9b3"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_document_last_crawl_target_id "
            "ON document (last_crawl_target_id)"
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_document_last_crawl_target_id")
