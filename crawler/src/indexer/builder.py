"""Build validated, immutable indexing inputs from stored documents.

Pipeline:
    IndexCandidate -> Document snapshot -> IndexDocument -> indexed_hash

This module reads PostgreSQL but never writes, commits, or builds TSVECTORs.
It does not claim work or lock rows. Before persisting a vector, the writer
must revalidate the source document under a concurrency-safe transaction.

Document.updated_at must change whenever index-relevant fields change.
Version/index hashing does not replace the writer's source-freshness check.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.documents import Document
from indexer.config import IndexerConfig
from indexer.errors import (
    IndexDocumentError,
    IndexDocumentTooLargeError,
    StaleIndexSourceError,
)
from indexer.schemas import IndexCandidate, IndexDocument

_HASH_DOMAIN = b"developers-eye:index-input:v1\x00"
_STRUCTURED_FIELDS = ("headings", "code_blocks", "tags")


def _normalize_prose(value: str | None, *, name: str, document_id: int) -> str:
    """Normalize line endings and Unicode; retain meaningful internal spaces."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise IndexDocumentError(
            f"{name} must be a string or None", document_id=document_id
        )
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def _metadata_items(
    metadata: dict[str, Any],
    key: str,
    *,
    document_id: int,
) -> tuple[str, ...]:
    """Validate the crawler's JSONB array contract without silent coercion."""
    raw = metadata.get(key, [])
    if not isinstance(raw, (list, tuple)):
        raise IndexDocumentError(
            f"metadata.{key} must be a list of strings", document_id=document_id
        )

    values: list[str] = []
    seen_tags: set[str] = set()

    for position, item in enumerate(raw):
        if not isinstance(item, str):
            raise IndexDocumentError(
                f"metadata.{key}[{position}] must be a string",
                document_id=document_id,
            )

        if key == "code_blocks":
            # Code indentation and line breaks affect meaning; do not collapse
            # whitespace or strip leading spaces from the first code line.
            normalized = item.replace("\r\n", "\n").replace("\r", "\n")
        else:
            normalized = _normalize_prose(
                item, name=f"metadata.{key}[{position}]", document_id=document_id
            )

        if not normalized.strip():
            continue

        if key == "tags":
            folded = normalized.casefold()
            if folded in seen_tags:
                continue
            seen_tags.add(folded)

        values.append(normalized)

    return tuple(values)


def prepare_index_document(document: Document, *, config: IndexerConfig) -> IndexDocument:
    """Convert a loaded, available Document into validated indexer input.

    No database operation occurs here. The resulting dataclass does not hold
    references to mutable ORM objects or JSONB containers.
    """
    if not isinstance(document, Document):
        raise TypeError("document must be a Document")
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")

    document_id = document.id
    if type(document_id) is not int or document_id <= 0:
        raise IndexDocumentError("invalid document ID", document_id=document_id)
    if not document.is_available:
        raise StaleIndexSourceError(f"document_id={document_id}: document is unavailable")

    metadata = document.metadata_
    if not isinstance(metadata, dict):
        raise IndexDocumentError("metadata must be a JSON object", document_id=document_id)

    extracted = {
        name: _metadata_items(metadata, name, document_id=document_id)
        for name in _STRUCTURED_FIELDS
    }

    # The crawler already normalizes content. Do not tokenize or stem here:
    # analyzer.py and vector.py own those responsibilities.
    result = IndexDocument(
        document_id=document_id,
        source_id=document.source_id,
        canonical_url=_normalize_prose(
            document.canonical_url, name="canonical_url", document_id=document_id
        ),
        document_type=_normalize_prose(
            document.document_type, name="document_type", document_id=document_id
        ),
        title=_normalize_prose(document.title, name="title", document_id=document_id),
        description=_normalize_prose(
            document.description, name="description", document_id=document_id
        ),
        body=_normalize_prose(document.body, name="body", document_id=document_id),
        content_hash=document.content_hash,
        source_updated_at=document.updated_at,
        headings=extracted["headings"],
        code_blocks=extracted["code_blocks"],
        tags=extracted["tags"],
    )

    if result.total_text_chars > config.max_document_chars:
        raise IndexDocumentTooLargeError(
            f"indexable text is {result.total_text_chars:,} characters; "
            f"maximum is {config.max_document_chars:,}",
            document_id=document_id,
        )

    return result


async def build_index_document(
    session: AsyncSession,
    candidate: IndexCandidate,
    *,
    config: IndexerConfig,
) -> IndexDocument:
    """Reload and validate the exact revision selected for indexing.

    Raises StaleIndexSourceError if the candidate was deleted, made
    unavailable, or changed after selection. The caller should reselect it.
    SQLAlchemy database errors propagate without losing their traceback.
    """
    if not isinstance(candidate, IndexCandidate):
        raise TypeError("candidate must be an IndexCandidate")
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")

    statement = select(Document).where(Document.id == candidate.document_id)
    document = await session.scalar(statement)

    if document is None:
        raise StaleIndexSourceError(
            f"document_id={candidate.document_id}: document no longer exists"
        )
    if not document.is_available:
        raise StaleIndexSourceError(
            f"document_id={candidate.document_id}: document is unavailable"
        )
    if document.updated_at != candidate.source_updated_at:
        raise StaleIndexSourceError(
            f"document_id={candidate.document_id}: updated after selection"
        )

    return prepare_index_document(document, config=config)


def calculate_index_hash(document: IndexDocument, *, config: IndexerConfig) -> str:
    """Return a version-prefixed hash of every field influencing our index.

    JSON encoding preserves field boundaries and array order. Timestamps and
    crawl observations are excluded: they do not affect the searchable input.
    Bump config.index_version whenever indexing rules/weights change.
    """
    if not isinstance(document, IndexDocument):
        raise TypeError("document must be an IndexDocument")
    if not isinstance(config, IndexerConfig):
        raise TypeError("config must be an IndexerConfig")

    payload = {
        "format": 1,
        "index_version": config.index_version,
        "text_search_config": config.text_search_config,
        "code_search_config": config.code_search_config,
        "document_id": document.document_id,
        "source_id": document.source_id,
        "canonical_url": document.canonical_url,
        "document_type": document.document_type,
        "title": document.title,
        "description": document.description,
        "body": document.body,
        "headings": document.headings,
        "code_blocks": document.code_blocks,
        "tags": document.tags,
        "content_hash": document.content_hash,
    }
    serialized = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(_HASH_DOMAIN + serialized).hexdigest()
    return f"{config.index_hash_prefix}{digest}"


__all__ = [
    "build_index_document",
    "prepare_index_document",
    "calculate_index_hash",
]
