"""Pydantic contracts for individual crawl attempts."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

AttemptOutcome = Literal["success", "failed", "blocked", "not_modified"]


class CrawlAttemptCreate(BaseModel):
    """Create an attempt; the database supplies started_at."""

    model_config = ConfigDict(extra="forbid")

    crawl_target_id: int = Field(gt=0)


class CrawlAttemptRead(CrawlAttemptCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    http_status: int | None = Field(default=None, ge=100, le=599)
    outcome: AttemptOutcome | None = None
    error_message: str | None = None
    bytes_received: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_finished_at(self) -> "CrawlAttemptRead":
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at must be at or after started_at")
        return self


class CrawlAttemptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finished_at: AwareDatetime | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    outcome: AttemptOutcome | None = None
    error_message: str | None = None
    bytes_received: int | None = Field(default=None, ge=0)
