"""Shared overview quota and cache/lease state; no provider I/O under row locks."""
from sqlalchemy import Float, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class OverviewBudget(Base):
    __tablename__ = "ai_overview_budget"
    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)


class OverviewCache(Base):
    __tablename__ = "ai_overview_cache"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[float] = mapped_column(Float, nullable=False)
    lease_until: Mapped[float] = mapped_column(Float, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (Index("ix_ai_overview_cache_expires_at", "expires_at"),)
