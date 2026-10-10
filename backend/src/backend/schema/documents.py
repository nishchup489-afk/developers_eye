"""Pydantic contracts for extracted documents.

External JSON uses `metadata`, while SQLAlchemy's Python attribute is `metadata_`.
Use `model_dump()` for ORM keyword arguments and `model_dump(by_alias=True)`
for JSON output when operating on a schema directly.
"""

from typing import Any

from pydantic import AliasChoices, AwareDatetime, BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int = Field(gt=0)
    last_crawl_target_id: int | None = Field(default=None, gt=0)
    canonical_url: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    body: str | None = None
    author: str | None = None
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata_", "metadata"),
        serialization_alias="metadata",
    )
    content_hash: str = Field(min_length=1)
    published_at: AwareDatetime | None = None


class DocumentRead(DocumentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    last_seen_at: AwareDatetime
    updated_at: AwareDatetime


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_crawl_target_id: int | None = Field(default=None, gt=0)
    canonical_url: str | None = Field(default=None, min_length=1)
    document_type: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    body: str | None = None
    author: str | None = None
    metadata_: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata_", "metadata"),
        serialization_alias="metadata",
    )
    content_hash: str | None = Field(default=None, min_length=1)
    published_at: AwareDatetime | None = None
