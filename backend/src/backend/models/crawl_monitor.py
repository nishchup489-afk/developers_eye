"""Durable, bounded-payload observability records for local crawler monitoring."""
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CrawlEvent(Base):
    __tablename__ = "crawl_event"
    __table_args__ = (Index("ix_crawl_event_attempt_id_id", "attempt_id", "id"),
                      Index("ix_crawl_event_created_at", "created_at"))
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("crawl_attempt.id", ondelete="CASCADE"))
    worker_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    stage: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class CrawlWorker(Base):
    __tablename__ = "crawl_worker"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    hostname: Mapped[str] = mapped_column(Text)
    pid: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    concurrency: Mapped[int] = mapped_column(Integer)
    batch_size: Mapped[int] = mapped_column(Integer)
    active_targets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
