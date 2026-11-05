"""Vocabulary entry used for typo-tolerant developer search."""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Identity, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class SearchTerm(Base):
    """One normalized term and its number of indexed source documents."""

    __tablename__ = "search_terms"

    term: Mapped[str] = mapped_column(Text, primary_key=True)
    document_frequency: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    __table_args__ = (
        CheckConstraint("length(term) BETWEEN 1 AND 128", name="ck_search_terms_length"),
        CheckConstraint(
            "document_frequency >= 0", name="ck_search_terms_document_frequency"
        ),
        Index(
            "ix_search_terms_trgm",
            "term",
            postgresql_using="gin",
            postgresql_ops={"term": "gin_trgm_ops"},
        ),
    )


class VocabularyChange(Base):
    """One document's added and removed terms, waiting to reach search_terms."""

    __tablename__ = "vocabulary_change"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    added: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    removed: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
