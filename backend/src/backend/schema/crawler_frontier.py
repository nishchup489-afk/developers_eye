"""Pydantic contracts for the durable crawl frontier."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

TargetKind = Literal["page", "sitemap", "rss", "api"]
TargetState = Literal["queued", "leased", "blocked", "disabled"]


class CrawlTargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(gt=0)
    fetch_url: str = Field(min_length=1)
    normalized_url: str = Field(min_length=1)
    kind: TargetKind = "page"
    priority: int = 0
    discovered_from_id: int | None = Field(default=None, gt=0)


class CrawlTargetRead(CrawlTargetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    state: TargetState
    next_fetch_at: AwareDatetime
    lease_until: AwareDatetime | None
    failure_count: int = Field(ge=0)
    last_fetched_at: AwareDatetime | None


class CrawlTargetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetch_url: str | None = Field(default=None, min_length=1)
    normalized_url: str | None = Field(default=None, min_length=1)
    kind: TargetKind | None = None
    state: TargetState | None = None
    priority: int | None = None
    next_fetch_at: AwareDatetime | None = None
    lease_until: AwareDatetime | None = None
    failure_count: int | None = Field(default=None, ge=0)
    last_fetched_at: AwareDatetime | None = None
    discovered_from_id: int | None = Field(default=None, gt=0)
