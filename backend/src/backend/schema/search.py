"""Public /search response contract, mirrored by frontend/lib/search.ts."""

from typing import Literal

from pydantic import BaseModel

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


class SearchResponseOut(BaseModel):
    query: str
    results: list[SearchResultOut]
