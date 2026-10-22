
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
)

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
    )

    # Document reference (Primary Key + Foreign Key)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "document.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    # PostgreSQL full-text search vector
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        nullable=False,
    )

    # Hash of the indexed content version
    indexed_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Last indexing timestamp
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
