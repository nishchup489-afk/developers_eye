
"""Database access for Developer's Eye retrieval vocabulary.

All SQL queries for vocabulary candidate discovery live here.

The repository is read-only at this stage.
Transactions are controlled by the caller.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.vocabulary_document_state import (
    VocabularyDocumentState,
)


# Completed indexer revisions have the format:
# v1:<64-character SHA-256 hash>
# v2:<64-character SHA-256 hash>
#
# This excludes temporary markers such as "reindex:pending".
COMPLETED_INDEX_HASH_PATTERN = (
    r"^v[1-9][0-9]*:[0-9a-f]{64}$"
)


async def fetch_pending_sync_rows(
    session: AsyncSession,
    *,
    limit: int,
    after_document_id: int,
) -> list[tuple[int, str]]:
    """Fetch indexed documents requiring vocabulary synchronization.

    A document is eligible when:
    - Its source document exists and is available.
    - Its search index contains a completed revision.
    - Its search index is not older than the source document.
    - No vocabulary state exists, or the indexed hash changed.

    Results are ordered by document ID for keyset pagination.

    No locks are acquired. The writer must revalidate revisions
    inside its own transaction before making changes.
    """

    stmt = (
        select(
            SearchIndex.document_id,
            SearchIndex.indexed_hash,
        )
        .join(
            Document,
            Document.id == SearchIndex.document_id,
        )
        .outerjoin(
            VocabularyDocumentState,
            VocabularyDocumentState.document_id
            == SearchIndex.document_id,
        )
        .where(
            SearchIndex.document_id > after_document_id,
            Document.is_available.is_(True),
            SearchIndex.indexed_at >= Document.updated_at,
            SearchIndex.indexed_hash.op("~")(
                COMPLETED_INDEX_HASH_PATTERN
            ),
            or_(
                VocabularyDocumentState.document_id.is_(None),
                VocabularyDocumentState.indexed_hash
                .is_distinct_from(SearchIndex.indexed_hash),
            ),
        )
        .order_by(SearchIndex.document_id.asc())
        .limit(limit)
    )

    result = await session.execute(stmt)

    return [
        (document_id, indexed_hash)
        for document_id, indexed_hash in result.all()
    ]


async def fetch_pending_removal_ids(
    session: AsyncSession,
    *,
    limit: int,
    after_document_id: int,
) -> list[int]:
    """Fetch documents whose vocabulary memberships need removal.

    A processed document requires cleanup when:
    - Its search_index row no longer exists.
    - Its source document no longer exists.
    - Its source document is no longer available.

    Only documents with an existing vocabulary state are selected.

    This function does not delete anything.
    """

    stmt = (
        select(VocabularyDocumentState.document_id)
        .outerjoin(
            SearchIndex,
            SearchIndex.document_id
            == VocabularyDocumentState.document_id,
        )
        .outerjoin(
            Document,
            Document.id
            == VocabularyDocumentState.document_id,
        )
        .where(
            VocabularyDocumentState.document_id
            > after_document_id,
            or_(
                SearchIndex.document_id.is_(None),
                Document.id.is_(None),
                Document.is_available.is_not(True),
            ),
        )
        .order_by(
            VocabularyDocumentState.document_id.asc()
        )
        .limit(limit)
    )

    result = await session.scalars(stmt)

    return list(result.all())




async def fetch_indexed_document(
    session: AsyncSession,
    *,
    document_id: int,
    indexed_hash: str,
) -> dict[str, object] | None:
    """Fetch the content of a successfully indexed document.

    Returns None if the document is missing, unavailable,
    stale, or its indexed revision has changed.

    Read-only. Transaction ownership remains with the caller.
    """

    if type(document_id) is not int or document_id <= 0:
        raise ValueError(
            "document_id must be a positive integer"
        )

    if not isinstance(indexed_hash, str) or not indexed_hash:
        raise ValueError(
            "indexed_hash must be a nonempty string"
        )

    stmt = (
        select(
            Document.id.label("document_id"),
            SearchIndex.indexed_hash.label("indexed_hash"),
            Document.title,
            Document.description,
            Document.body,
        )
        .join(
            SearchIndex,
            SearchIndex.document_id == Document.id,
        )
        .where(
            Document.id == document_id,
            Document.is_available.is_(True),
            SearchIndex.indexed_hash == indexed_hash,
            SearchIndex.indexed_hash.op("~")(
                COMPLETED_INDEX_HASH_PATTERN
            ),
            SearchIndex.indexed_at >= Document.updated_at,
        )
    )

    result = await session.execute(stmt)
    row = result.mappings().one_or_none()

    if row is None:
        return None

    return {
        **dict(row),
        "headings": (),
        "code_blocks": (),
        "tags": (),
    }
