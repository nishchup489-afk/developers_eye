from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Identity,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base



# --------------------------------------------
#   EXAMPLE RECORD 
# -------------------------------------------

# source = Source(
#     slug="github",
#     name="GitHub",
#     kind="api",
#     base_url="https://api.github.com",
#     allowed_hosts=["api.github.com"],
#     crawl_interval_seconds=3600,
#     config={
#         "max_depth": 3,
#         "rate_limit": 30,
#         "requires_auth": True,
#     },
# )


# ---------------------------------------------

class Source(Base):
    __tablename__ = "source"

    __table_args__ = (
        CheckConstraint(
            "kind IN ('website', 'rss', 'api')",
            name="ck_source_kind",
        ),
        CheckConstraint(
            "crawl_interval_seconds > 0",
            name="ck_source_crawl_interval",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    slug: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    base_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    allowed_hosts: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )

    crawl_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3600,
        server_default=text("3600"),
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )