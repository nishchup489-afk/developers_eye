
"""Shared data contracts for the Developer's Eye search pipeline.

This module defines data structures only. It does not execute
queries, rank documents, generate snippets, or access the database.
"""

from dataclasses import dataclass
from math import isfinite


def _validate_document_id(document_id: int) -> None:
    if type(document_id) is not int or document_id <= 0:
        raise ValueError("document_id must be a positive integer")


def _validate_score(
    score: float,
    *,
    name: str,
    non_negative: bool = False,
) -> None:
    if isinstance(score, bool) or not isinstance(
        score, (int, float)
    ):
        raise TypeError(f"{name} must be numeric")

    if not isfinite(score):
        raise ValueError(f"{name} must be finite")

    if non_negative and score < 0:
        raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievalHit:
    """Raw candidate returned by PostgreSQL retrieval engines.

    Scores are preliminary retrieval scores, not final BM25 scores.
    A zero score means the corresponding retrieval path did not
    contribute a positive score for this candidate.
    """

    document_id: int
    search_rank: float = 0.0
    code_rank: float = 0.0

    def __post_init__(self) -> None:
        _validate_document_id(self.document_id)
        _validate_score(
            self.search_rank,
            name="search_rank",
            non_negative=True,
        )
        _validate_score(
            self.code_rank,
            name="code_rank",
            non_negative=True,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RankedHit:
    """Deduplicated document candidate after final ranking."""

    document_id: int
    score: float
    search_rank: float = 0.0
    code_rank: float = 0.0

    def __post_init__(self) -> None:
        _validate_document_id(self.document_id)
        _validate_score(self.score, name="score")
        _validate_score(
            self.search_rank,
            name="search_rank",
            non_negative=True,
        )
        _validate_score(
            self.code_rank,
            name="code_rank",
            non_negative=True,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchResult:
    """Public-facing result after metadata and snippet enrichment."""

    document_id: int
    title: str
    url: str
    score: float
    snippet: str = ""
    document_type: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        _validate_document_id(self.document_id)
        _validate_score(self.score, name="score")

        for name in ("title", "url", "snippet"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string")

        for name in ("document_type", "source"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None")


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchResponse:
    """Final collection returned by the search service.

    total=None means the total matching document count is unknown.
    It is not necessarily equal to the number of returned results.
    """

    query: str
    results: tuple[SearchResult, ...]
    total: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("query must be a non-empty string")

        if not isinstance(self.results, tuple):
            raise TypeError("results must be a tuple")

        if not all(
            isinstance(result, SearchResult)
            for result in self.results
        ):
            raise TypeError("results must contain SearchResult objects")

        if self.total is not None:
            if type(self.total) is not int or self.total < 0:
                raise ValueError("total must be a non-negative integer")

            if self.total < len(self.results):
                raise ValueError(
                    "total cannot be smaller than returned results"
                )
