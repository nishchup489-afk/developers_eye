"""Track crawl depth and backfill existing discovery chains."""
from alembic import op
import sqlalchemy as sa

revision = 'c72f318bd923'
down_revision = 'b61e204ac812'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('crawl_target', sa.Column('depth', sa.Integer(), nullable=False, server_default='0'))
    # Broken/cyclic historical chains remain beyond scope rather than becoming new roots.
    op.execute('UPDATE crawl_target SET depth = 2147483647 WHERE discovered_from_id IS NOT NULL')
    op.execute('''WITH RECURSIVE tree AS (
        SELECT id, 0 AS depth, ARRAY[id] AS visited FROM crawl_target WHERE discovered_from_id IS NULL
        UNION ALL
        SELECT child.id, tree.depth + 1, tree.visited || child.id
        FROM crawl_target child JOIN tree ON child.discovered_from_id = tree.id
        WHERE NOT child.id = ANY(tree.visited)
    ) UPDATE crawl_target target SET depth = tree.depth FROM tree WHERE target.id = tree.id''')
    op.create_check_constraint('ck_crawl_target_depth', 'crawl_target', 'depth >= 0')


def downgrade():
    op.drop_constraint('ck_crawl_target_depth', 'crawl_target', type_='check')
    op.drop_column('crawl_target', 'depth')
