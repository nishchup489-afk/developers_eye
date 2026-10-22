"""Pydantic contracts for cached robots.txt responses."""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class RobotsCacheCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=1)
    raw_content: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    fetched_at: AwareDatetime | None = None
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def check_expiry(self) -> "RobotsCacheCreate":
        if self.fetched_at is not None and self.expires_at <= self.fetched_at:
            raise ValueError("expires_at must be later than fetched_at")
        return self


class RobotsCacheRead(RobotsCacheCreate):
    model_config = ConfigDict(from_attributes=True)

    fetched_at: AwareDatetime


class RobotsCacheUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_content: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    fetched_at: AwareDatetime | None = None
    expires_at: AwareDatetime | None = None
