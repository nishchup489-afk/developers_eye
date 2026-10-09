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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CrawlTarget(Base):
    __tablename__ = "crawl_target"

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "normalized_url",
            name="uq_crawl_target_source_url",
        ),
        CheckConstraint(
            "kind IN ('page', 'sitemap', 'rss', 'api')",
            name="ck_crawl_target_kind",
        ),
        CheckConstraint(
            "state IN ('queued', 'leased', 'blocked', 'disabled')",
            name="ck_crawl_target_state",
        ),
        CheckConstraint(
            "failure_count >= 0",
            name="ck_crawl_target_failure_count",
        ),
        Index(
            "ix_crawl_target_frontier",
            "state",
            "next_fetch_at",
            "priority",
        ),
    )

    # Primary Key
    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    # Owning Source
    source_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("source.id"),
        nullable=False,
        index=True,
    )

    # Actual URL to request
    fetch_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Normalized URL for deduplication
    normalized_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Target Type
    kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'page'"),
    )

    # Frontier State
    state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
    )

    # Fetch Priority
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    # Next Eligible Fetch
    next_fetch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Worker Lease Expiration
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Consecutive Failures
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    # Last Successful/Attempted Fetch
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Parent Discovery Target
    discovered_from_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "crawl_target.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )