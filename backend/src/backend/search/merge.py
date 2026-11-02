
"""Merge and deduplicate retrieval candidates by document ID.

Combines text and code retrieval hits while preserving their
independent scores. Final relevance ranking is handled separately.
"""

from __future__ import annotations

from collections.abc import Iterable

from backend.search.types import RetrievalHit


def merge_hits(
    *hit_groups: Iterable[RetrievalHit],
) -> list[RetrievalHit]:
    """Merge retrieval results into unique document candidates.

    Rules:
        - Each document ID appears only once.
        - Text and code scores remain separate.
        - Repeated scores within a channel use the maximum.
        - Output is sorted by document ID for deterministic behavior.
        - Inputs are never modified.
        - Final relevance ranking is not performed here.
    """
    merged: dict[int, RetrievalHit] = {}

    for hits in hit_groups:
        for hit in hits:
            if not isinstance(hit, RetrievalHit):
                raise TypeError(
                    "All hits must be RetrievalHit instances"
                )

            existing = merged.get(hit.document_id)

            if existing is None:
                merged[hit.document_id] = hit
                continue

            merged[hit.document_id] = RetrievalHit(
                document_id=hit.document_id,
                search_rank=max(
                    existing.search_rank,
                    hit.search_rank,
                ),
                code_rank=max(
                    existing.code_rank,
                    hit.code_rank,
                ),
            )

    return [
        merged[document_id]
        for document_id in sorted(merged)
    ]
