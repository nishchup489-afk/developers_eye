"""Typed vocabulary, fuzzy candidate and query correction contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    term: str = Field(min_length=1, max_length=128)
    document_frequency: int = Field(ge=0)


class FuzzyCandidate(SearchTermRead):
    similarity: float = Field(ge=0.0, le=1.0)


class TermCorrection(BaseModel):
    original: str = Field(min_length=1)
    replacement: str = Field(min_length=1)
    similarity: float = Field(ge=0.0, le=1.0)
    edit_distance: int = Field(ge=0)


class QueryCorrection(BaseModel):
    original_query: str
    suggested_query: str
    corrections: list[TermCorrection] = Field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.original_query != self.suggested_query
