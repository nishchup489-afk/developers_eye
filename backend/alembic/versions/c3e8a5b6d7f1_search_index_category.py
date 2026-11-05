"""Store each document's result category so filters apply inside retrieval.

Revision ID: c3e8a5b6d7f1
Revises: b7d2f4a9c1e3
"""
from alembic import op

revision = "c3e8a5b6d7f1"
down_revision = "b7d2f4a9c1e3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE search_index ADD COLUMN category text NOT NULL DEFAULT 'articles'")
    # One-time copy of backend.search.categories.categorize for existing rows.
    op.execute(r"""
        UPDATE search_index si SET category = CASE
            WHEN d.host ~ '(^|\.)(github|gitlab)\.com$' THEN 'github'
            WHEN d.host ~ '(^|\.)(stackoverflow|stackexchange)\.com$' THEN 'stackoverflow'
            WHEN d.host ~ '(^|\.)reddit\.com$' THEN 'reddit'
            WHEN d.host ~ '(^|\.)(leetcode\.com|hackerrank\.com|exercism\.org|codewars\.com)$' THEN 'practice'
            WHEN d.document_type = 'documentation' THEN 'docs'
            WHEN d.document_type = 'question' THEN 'stackoverflow'
            WHEN d.document_type IN ('issue', 'repository') THEN 'github'
            WHEN d.document_type = 'event' THEN 'events'
            ELSE 'articles'
        END
        FROM (
            SELECT id, document_type,
                   lower(substring(canonical_url from '^[a-zA-Z]+://([^/:?#]+)')) AS host
            FROM document
        ) d
        WHERE d.id = si.document_id
    """)
    op.execute("CREATE INDEX ix_search_index_category ON search_index (category)")


def downgrade():
    op.execute("DROP INDEX ix_search_index_category")
    op.execute("ALTER TABLE search_index DROP COLUMN category")
