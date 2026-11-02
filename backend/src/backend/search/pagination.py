"""Bounded, deterministic offset pagination of ranked candidate hits."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.search.config import SearchConfig
from backend.search.types import RankedHit


@dataclass(frozen=True, slots=True)
class PaginatedHits:
    hits: tuple[RankedHit, ...]
    page: int
    limit: int
    offset: int
    total_candidates: int
    total_pages: int
    has_next: bool
    has_previous: bool


def paginate_hits(
    ranked_hits: Sequence[RankedHit],
    *,
    page: int = 1,
    limit: int | None = None,
    config: SearchConfig | None = None,
) -> PaginatedHits:
    """Slice a previously sorted and filtered candidate pool; never sort here."""
    if config is None:
        config = SearchConfig()
    elif not isinstance(config, SearchConfig):
        raise TypeError("config must be SearchConfig")
    if not isinstance(ranked_hits, Sequence) or isinstance(ranked_hits, (str, bytes)):
        raise TypeError("ranked_hits must be a sequence")
    if any(not isinstance(hit, RankedHit) for hit in ranked_hits):
        raise TypeError("All candidates must be RankedHit instances")
    if type(page) is not int or page < 1:
        raise ValueError("page must be a positive integer")
    if limit is None:
        limit = config.default_limit
    if type(limit) is not int or not 1 <= limit <= config.max_limit:
        raise ValueError(f"limit must be between 1 and {config.max_limit}")

    offset = (page - 1) * limit
    if offset > config.max_offset:
        raise ValueError(f"offset cannot exceed {config.max_offset}")

    total = len(ranked_hits)
    page_count = (total + limit - 1) // limit
    hits = tuple(ranked_hits[offset:offset + limit])
    return PaginatedHits(
        hits=hits,
        page=page,
        limit=limit,
        offset=offset,
        total_candidates=total,
        total_pages=page_count,
        has_next=offset + limit < total,
        has_previous=page > 1 and total > 0,
    )


__all__ = ["PaginatedHits", "paginate_hits"]
