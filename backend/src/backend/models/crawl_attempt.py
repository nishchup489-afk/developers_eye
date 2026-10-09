
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CrawlAttempt(Base):
    __tablename__ = "crawl_attempt"

    __table_args__ = (
        CheckConstraint(
            "outcome IS NULL OR outcome IN "
            "('success', 'failed', 'blocked', 'not_modified')",
            name="ck_crawl_attempt_outcome",
        ),
        CheckConstraint(
            "bytes_received >= 0",
            name="ck_crawl_attempt_bytes",
        ),
        CheckConstraint(
            "http_status BETWEEN 100 AND 599",
            name="ck_crawl_attempt_http_status",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_crawl_attempt_time",
        ),
        Index(
            "ix_crawl_attempt_target_started",
            "crawl_target_id",
            "started_at",
        ),
    )

    # Unique attempt ID
    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    # Target being fetched
    crawl_target_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_target.id"),
        nullable=False,
    )

    # Attempt start time
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Attempt completion time
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # HTTP response status
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Attempt outcome
    outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Error description
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Response body size in bytes
    bytes_received: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
