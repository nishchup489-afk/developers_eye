"""Retain unavailable document history without serving stale search entries."""
from alembic import op
import sqlalchemy as sa

revision = 'e94b530df145'
down_revision = 'd83a429ce034'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('document', sa.Column('is_available', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('document', sa.Column('unavailable_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('document', sa.Column('unavailable_http_status', sa.Integer(), nullable=True))
    op.execute('''WITH latest AS (
        SELECT DISTINCT ON (crawl_target_id) crawl_target_id, http_status, finished_at
        FROM crawl_attempt WHERE finished_at IS NOT NULL
        ORDER BY crawl_target_id, started_at DESC, id DESC
    ) UPDATE document SET is_available = false, unavailable_at = latest.finished_at,
        unavailable_http_status = latest.http_status
    FROM latest WHERE document.last_crawl_target_id = latest.crawl_target_id
        AND latest.http_status IN (404, 410)''')
    op.execute('DELETE FROM search_index USING document WHERE search_index.document_id = document.id AND NOT document.is_available')


def downgrade():
    op.drop_column('document', 'unavailable_http_status')
    op.drop_column('document', 'unavailable_at')
    op.drop_column('document', 'is_available')
