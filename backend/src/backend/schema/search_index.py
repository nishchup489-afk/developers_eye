"""Pydantic contracts for indexing-worker data.

`search_vector` is PostgreSQL TSVECTOR-formatted data, not raw webpage text.
Normally construct it in PostgreSQL with `to_tsvector(...)`, rather than
passing unprocessed body text as `search_vector`.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class SearchIndexCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int = Field(gt=0)
    search_vector: str = Field(min_length=1)
    indexed_hash: str = Field(min_length=1)


class SearchIndexRead(SearchIndexCreate):
    model_config = ConfigDict(from_attributes=True)

    indexed_at: AwareDatetime


class SearchIndexUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_vector: str | None = Field(default=None, min_length=1)
    indexed_hash: str | None = Field(default=None, min_length=1)
    indexed_at: AwareDatetime | None = None
