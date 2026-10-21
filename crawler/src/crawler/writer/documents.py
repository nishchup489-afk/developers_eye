"""Persist processed documents using a PostgreSQL upsert.

A document is uniquely identified by canonical_url. The Worker supplies a
verified source/target and owns the transaction; this module only writes SQL.
"""

from __future__ import annotations

from sqlalchemy import case, func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from crawler.processing import ProcessedDocument


async def upsert_document(
    session: AsyncSession,
    document: ProcessedDocument,
    *,
    source_id: int,
    crawl_target_id: int,
) -> int:
    """Insert a new document, or refresh an existing document with the same URL.

    - last_seen_at is refreshed on every successful observation.
    - updated_at changes only if stored document data actually changed.
    - The returned ID is valid for both INSERT and UPDATE outcomes.

    Note: one canonical URL has one owning source in the current schema.
    When two sources crawl that same URL, the most recently written source wins.
    """
    if not isinstance(document, ProcessedDocument):
        raise TypeError("document must be a ProcessedDocument")
    if type(source_id) is not int or source_id <= 0:
        raise ValueError("source_id must be a positive integer")
    if type(crawl_target_id) is not int or crawl_target_id <= 0:
        raise ValueError("crawl_target_id must be a positive integer")
    if not isinstance(document.canonical_url, str) or not document.canonical_url:
        raise ValueError("document.canonical_url must be nonempty")
    if not isinstance(document.title, str) or not document.title.strip():
        raise ValueError("document.title must be nonempty")
    if not isinstance(document.content_hash, str) or not document.content_hash:
        raise ValueError("document.content_hash must be nonempty")
    if not isinstance(document.metadata, dict):
        raise TypeError("document.metadata must be a dict for JSONB")

    # Preserve structured developer content in JSONB metadata.

    metadata = {
        **document.metadata,
        "headings": list(document.headings),
        "code_blocks": list(document.code_blocks),
        "tags": list(document.tags),
    }

    statement = insert(Document).values(
        source_id=source_id,
        last_crawl_target_id=crawl_target_id,
        canonical_url=document.canonical_url,
        document_type=document.document_type,
        title=document.title,
        description=document.description,
        body=document.body,
        author=document.author,
        metadata_=metadata,
        content_hash=document.content_hash,
        published_at=document.published_at,
        last_seen_at=func.clock_timestamp(),
        is_available=True,
        updated_at=func.clock_timestamp(),
    )

    incoming = statement.excluded

    # Compare actual persisted fields, not just the hash: author/metadata/date
    # can change even when the text hash stays identical.
    changed = or_(
        Document.content_hash.is_distinct_from(incoming.content_hash),
        Document.document_type.is_distinct_from(incoming.document_type),
        Document.title.is_distinct_from(incoming.title),
        Document.description.is_distinct_from(incoming.description),
        Document.body.is_distinct_from(incoming.body),
        Document.author.is_distinct_from(incoming.author),
        Document.published_at.is_distinct_from(incoming.published_at),
        Document.metadata_.is_distinct_from(incoming["metadata"]),
    )

    statement = (
        statement.on_conflict_do_update(
            index_elements=[Document.canonical_url],
            set_={
                "source_id": incoming.source_id,
                "last_crawl_target_id": incoming.last_crawl_target_id,
                "document_type": incoming.document_type,
                "title": incoming.title,
                "description": incoming.description,
                "body": incoming.body,
                "author": incoming.author,
                Document.metadata_: incoming["metadata"],
                "content_hash": incoming.content_hash,
                "published_at": incoming.published_at,
                "last_seen_at": func.clock_timestamp(),
                "is_available": True,
                "unavailable_at": None,
                "unavailable_http_status": None,
                "updated_at": case(
                    (changed, func.clock_timestamp()),
                    else_=Document.updated_at,
                ),
            },
        )
        .returning(Document.id)
    )

    saved_id = await session.scalar(statement)
    if saved_id is None:
        raise RuntimeError("Database did not return a document ID")
    return saved_id
