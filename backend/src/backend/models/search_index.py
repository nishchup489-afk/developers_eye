"""Stored PostgreSQL full-text index for a crawler Document."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class SearchIndex(Base):
    __tablename__ = "search_index"

    __table_args__ = (
        Index(
            "ix_search_index_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        Index(
            "ix_search_index_code_vector",
            "code_vector",
            postgresql_using="gin",
        ),
    )

    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("document.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Existing search field: used for English-language documents.
    search_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=False)

    # Separate code-oriented search field: simple PostgreSQL text search.
    code_vector: Mapped[str] = mapped_column(TSVECTOR, nullable=False)

    indexed_hash: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
