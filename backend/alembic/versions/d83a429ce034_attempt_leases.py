"""Associate attempts with the exact frontier claim that created them."""
from alembic import op
import sqlalchemy as sa

revision = 'd83a429ce034'
down_revision = 'c72f318bd923'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('crawl_attempt', sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('crawl_attempt', 'lease_until')
