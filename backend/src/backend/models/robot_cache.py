from datetime import datetime

from sqlalchemy import (
    Text,
    Integer,
    DateTime,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class RobotsCache(Base):
    __tablename__ = "robots_cache"

    __table_args__ = (
        CheckConstraint(
            "expires_at > fetched_at",
            name="ck_robots_cache_expiration",
        ),
    )

    # Unique website origin
    origin: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )

    # Raw robots.txt content
    raw_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # HTTP response status
    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Last retrieval timestamp
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Cache expiration timestamp
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )