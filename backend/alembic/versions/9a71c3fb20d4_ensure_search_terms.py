"""Create the fuzzy vocabulary table omitted by two earlier empty revisions.

Revision ID: 9a71c3fb20d4
Revises: da03da123834

The earlier migrations were already stamped in some installations; add a
forward-only repair revision instead of editing applied migration history.
"""
from alembic import op

revision = "9a71c3fb20d4"
down_revision = "da03da123834"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.search_terms (
            term TEXT PRIMARY KEY,
            document_frequency INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT ck_search_terms_length
                CHECK (length(term) BETWEEN 1 AND 128),
            CONSTRAINT ck_search_terms_document_frequency
                CHECK (document_frequency >= 0)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_search_terms_trgm
        ON public.search_terms USING gin (term gin_trgm_ops)
    """)


def downgrade() -> None:
    # Leave existing installations' vocabulary data alone. This repair
    # migration may have encountered a table created manually before upgrade.
    # Dropping it on downgrade would silently destroy that pre-existing data.
    pass
