
"""Candidate selection for Developer's Eye retrieval vocabulary.

The selector owns pagination validation and candidate construction.

All database queries are delegated to repository.py.
No SQLAlchemy statements are constructed here.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from retrieval_vocabulary.errors import (
    VocabularyValidationError,
)
from retrieval_vocabulary.repository import (
    fetch_pending_removal_ids,
    fetch_pending_sync_rows,
)
from retrieval_vocabulary.schema import (
    VocabularyAction,
    VocabularyCandidate,
)


MAX_BATCH_SIZE = 10_000


def _validate_selection(
    limit: int,
    after_document_id: int,
) -> None:
    """Validate pagination parameters.

    Booleans are explicitly rejected because bool is a subclass
    of int in Python.
    """

    if type(limit) is not int:
        raise VocabularyValidationError(
            "limit must be an integer"
        )

    if not 1 <= limit <= MAX_BATCH_SIZE:
        raise VocabularyValidationError(
            f"limit must be between 1 and {MAX_BATCH_SIZE}"
        )

    if type(after_document_id) is not int:
        raise VocabularyValidationError(
            "after_document_id must be an integer"
        )

    if after_document_id < 0:
        raise VocabularyValidationError(
            "after_document_id cannot be negative"
        )


async def select_sync_candidates(
    session: AsyncSession,
    *,
    limit: int = 100,
    after_document_id: int = 0,
) -> list[VocabularyCandidate]:
    """Select new or outdated vocabulary documents.

    Only completed and current search-index revisions qualify.

    Returns an empty list when no matching documents exist.
    """

    _validate_selection(limit, after_document_id)

    rows = await fetch_pending_sync_rows(
        session,
        limit=limit,
        after_document_id=after_document_id,
    )

    return [
        VocabularyCandidate(
            document_id=document_id,
            action=VocabularyAction.SYNC,
            indexed_hash=indexed_hash,
        )
        for document_id, indexed_hash in rows
    ]


async def select_removal_candidates(
    session: AsyncSession,
    *,
    limit: int = 100,
    after_document_id: int = 0,
) -> list[VocabularyCandidate]:
    """Select vocabulary documents requiring cleanup.

    Returns candidates for previously processed documents that
    are no longer available or no longer indexed.

    The writer owns actual deletion and frequency updates.
    """

    _validate_selection(limit, after_document_id)

    document_ids = await fetch_pending_removal_ids(
        session,
        limit=limit,
        after_document_id=after_document_id,
    )

    return [
        VocabularyCandidate(
            document_id=document_id,
            action=VocabularyAction.REMOVE,
            indexed_hash=None,
        )
        for document_id in document_ids
    ]
