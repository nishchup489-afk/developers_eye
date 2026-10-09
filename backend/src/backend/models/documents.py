
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Document(Base):
    __tablename__ = "document"

    __table_args__ = (
        Index(
            "ix_document_type_published",
            "document_type",
            "published_at",
        ),
    )

    # Unique document ID
    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    # Originating source
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("source.id"),
        nullable=False,
        index=True,
    )

    # Most recent crawl target
    last_crawl_target_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "crawl_target.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    # Canonical document URL
    canonical_url: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    # Document category
    document_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Search result title
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Short document summary
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Cleaned extracted content
    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Author or creator
    author: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Platform-specific attributes
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    # Hash used for detecting content changes
    content_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Original publication time
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Most recent observation
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Last actual content update
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
