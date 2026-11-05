from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CrawlHost(Base):
    """Shared politeness state for one hostname, across all crawler processes.

    next_allowed_at is the earliest moment a new request to this host may start.
    A request holds the host by pushing it forward, and finishing the request
    sets it to now + the minimum gap. A crashed worker's hold simply expires.
    """

    __tablename__ = "crawl_host"
    __table_args__ = {"postgresql_with": {"fillfactor": 50}}

    host: Mapped[str] = mapped_column(Text, primary_key=True)
    next_allowed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
