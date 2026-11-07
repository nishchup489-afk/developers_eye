"""One API process's search outcomes for one minute."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class SearchMinute(Base):
    __tablename__ = "search_minute"

    minute: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    process: Mapped[str] = mapped_column(Text, primary_key=True)
    successful: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    invalid: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    busy: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    timed_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    database_errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    engine_errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    server_errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_sum_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    # Successful searches per LATENCY_BOUNDS_MS bucket, with one overflow bucket at the end.
    latency_buckets: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
