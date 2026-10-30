"""Public /search response contract, mirrored by frontend/lib/search.ts."""

from typing import Literal

from pydantic import BaseModel

SearchCategory = Literal[
    "docs", "github", "stackoverflow", "reddit", "articles", "events", "practice"
]


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
