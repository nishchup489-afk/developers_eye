"""Backend-owned evidence and cited overview contracts (ADR-0049)."""
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class OverviewSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[StrictInt, Field(ge=1, le=4)]
    title: str = Field(max_length=120)
    url: str = Field(max_length=1500)
    snippet: str = Field(max_length=350)
    kind: str

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Invalid source URL")
        if len(value.encode("utf-8")) > 1500:
            raise ValueError("Source URL too long")
        return value


class OverviewContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)
    sources: list[OverviewSource] = Field(min_length=1, max_length=4)
    expires: float


class OverviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=24000)


class OverviewParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=700)
    sources: list[StrictInt] = Field(min_length=1, max_length=4)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Empty paragraph")
        return value.strip()


class ModelOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    paragraphs: list[OverviewParagraph] = Field(max_length=3)


class AIOverview(ModelOverview):
    sources: list[OverviewSource]


class OverviewResponse(BaseModel):
    overview: AIOverview | None = None
    error: str | None = Field(default=None, exclude_if=lambda value: value is None)
