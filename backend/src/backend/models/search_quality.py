"""Search diagnostics and human relevance judging (ADR-0057).

search_slow_query keeps only searches that crossed SEARCH_SLOW_QUERY_MS or
timed out, so ordinary searches still write nothing (ADR-0044). The relevance
tables hold the human-judged evaluation set that the admin page edits.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, SmallInteger, Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class SearchSlowQuery(Base):
    __tablename__ = "search_slow_query"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    process: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer)
    # Milliseconds per finished stage, plus the stage running when the search stopped.
    stages: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    stopped_in: Mapped[str | None] = mapped_column(Text)


class RelevanceQuery(Base):
    __tablename__ = "relevance_query"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'all'"))
    stratum: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    # Optional result filter, e.g. "docs" or "github", as on the public search page.
    source: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    no_relevant_documents: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("id ~ '^[A-Za-z0-9_-]{1,32}$'", name="ck_relevance_query_id"),
        CheckConstraint("mode IN ('all', 'text', 'code')", name="ck_relevance_query_mode"),
        CheckConstraint("length(query) BETWEEN 1 AND 256", name="ck_relevance_query_length"),
    )


class RelevanceRun(Base):
    """One pooled capture: both orderings of the same candidate set, by URL."""

    __tablename__ = "relevance_run"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    query_id: Mapped[str] = mapped_column(Text, ForeignKey("relevance_query.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # [{"url", "title", "bm25_rank", "postgres_rank"}] for every candidate.
    documents: Mapped[list] = mapped_column(JSONB, nullable=False)


class RelevanceJudgment(Base):
    __tablename__ = "relevance_judgment"

    query_id: Mapped[str] = mapped_column(Text, ForeignKey("relevance_query.id", ondelete="CASCADE"), primary_key=True)
    url: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    # pool: from a top-10 union; added: a relevant page a judge found independently.
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pool'"))
    judged_by: Mapped[str | None] = mapped_column(Text)
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("grade IS NULL OR grade BETWEEN 0 AND 3", name="ck_relevance_judgment_grade"),
        CheckConstraint("origin IN ('pool', 'added')", name="ck_relevance_judgment_origin"),
        CheckConstraint("url ~ '^https?://'", name="ck_relevance_judgment_url"),
    )
