"""Public /search response contract, mirrored by frontend/lib/search.ts."""

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

SearchCategory = Literal[
    "docs", "github", "stackoverflow", "reddit", "articles", "events", "practice"
]
# What a request may filter by: any category, or the combined Discussions view.
SearchFilter = SearchCategory | Literal["discussions"]


class SearchResultOut(BaseModel):
    title: str
    source: SearchCategory
    url: str
    snippet: str
    score: float
    tags: list[str] = []
    # Raw document type (documentation, issue, ...) kept separate from `source`.
    type: str
    language: str | None = Field(default=None, exclude_if=lambda value: value is None)
    version: str | None = Field(default=None, exclude_if=lambda value: value is None)
    last_seen_at: datetime | None = Field(default=None, exclude_if=lambda value: value is None)
    related_variants: int | None = Field(default=None, exclude_if=lambda value: value is None)
    snippet_is_code: bool = Field(default=False, exclude_if=lambda value: not value)


class SearchResponseOut(BaseModel):
    query: str
    results: list[SearchResultOut]
    overview_token: str | None = Field(default=None, exclude_if=lambda value: value is None)
