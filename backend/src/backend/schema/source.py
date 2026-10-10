"""Pydantic contracts for registered crawl sources."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

SourceKind = Literal["website", "rss", "api"]


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1)
    kind: SourceKind
    base_url: str = Field(min_length=1)
    allowed_hosts: list[str] = Field(min_length=1)
    crawl_interval_seconds: int = Field(default=3600, gt=0)
    is_enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class SourceRead(SourceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    created_at: AwareDatetime


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str | None = Field(default=None, min_length=1, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str | None = Field(default=None, min_length=1)
    kind: SourceKind | None = None
    base_url: str | None = Field(default=None, min_length=1)
    allowed_hosts: list[str] | None = Field(default=None, min_length=1)
    crawl_interval_seconds: int | None = Field(default=None, gt=0)
    is_enabled: bool | None = None
    config: dict[str, Any] | None = None
