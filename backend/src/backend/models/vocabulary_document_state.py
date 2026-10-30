
"""Tracks successfully processed vocabulary document revisions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class VocabularyDocumentState(Base):
    __tablename__ = "vocabulary_document_state"

    document_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    indexed_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
