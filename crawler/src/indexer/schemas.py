"""Data contracts between the selector, builder, writer, and worker.

These types are independent of SQLAlchemy ORM instances. Search vectors are
created inside PostgreSQL and are intentionally NOT represented as raw text.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from indexer.errors import IndexDocumentError

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _positive_id(value: object, *, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise IndexDocumentError(f"{name} must be a positive integer")


def _aware_datetime(value: object, *, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise IndexDocumentError(f"{name} must be a timezone-aware datetime")


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexCandidate:
    """Lightweight selection result; reload the row before indexing."""

    document_id: int
    source_updated_at: datetime

    def __post_init__(self) -> None:
        _positive_id(self.document_id, name="document_id")
        _aware_datetime(self.source_updated_at, name="source_updated_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexDocument:
    """Validated snapshot of one available, stored document.

    The builder must convert Document.metadata_ JSONB headings, code_blocks,
    and tags into tuples of strings before constructing this object. A document
    with no tags is valid. The source content_hash does NOT include tags.
    """

    document_id: int
    source_id: int
    canonical_url: str
    document_type: str
    title: str
    content_hash: str
    source_updated_at: datetime
    description: str = ""
    body: str = ""
    headings: tuple[str, ...] = ()
    code_blocks: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive_id(self.document_id, name="document_id")
        _positive_id(self.source_id, name="source_id")
        _aware_datetime(self.source_updated_at, name="source_updated_at")

        if not isinstance(self.canonical_url, str) or not self.canonical_url:
            self._invalid("canonical_url must be a nonempty string")
        if any(ch.isspace() or ord(ch) < 32 or ch == "\\" for ch in self.canonical_url):
            self._invalid("canonical_url contains invalid characters")
        try:
            parsed = urlsplit(self.canonical_url)
            host = parsed.hostname
            credentials = parsed.username is not None or parsed.password is not None
            _ = parsed.port  # Reject malformed ports if present.
        except ValueError as exc:
            raise IndexDocumentError(
                "canonical_url is malformed", document_id=self.document_id
            ) from exc
        if parsed.scheme.lower() not in {"http", "https"} or not host or credentials:
            self._invalid("canonical_url must be an absolute HTTP(S) URL without credentials")

        for name in ("document_type", "title", "description", "body"):
            value = getattr(self, name)
            if not isinstance(value, str):
                self._invalid(f"{name} must be a string")
        if not self.document_type.strip():
            self._invalid("document_type must not be blank")
        if not self.title.strip():
            self._invalid("title must not be blank")

        for name in ("headings", "code_blocks", "tags"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not all(
                isinstance(value, str) for value in values
            ):
                self._invalid(f"{name} must be a tuple of strings")
        if not self.body.strip() and not any(block.strip() for block in self.code_blocks):
            self._invalid("document must contain body text or a code block")

        if not isinstance(self.content_hash, str) or not _SHA256.fullmatch(self.content_hash):
            self._invalid("content_hash must be a lowercase SHA-256 hex digest")

    def _invalid(self, message: str) -> None:
        raise IndexDocumentError(message, document_id=self.document_id)

    @property
    def total_text_chars(self) -> int:
        """Upper-bound input budget checked against config.max_document_chars."""
        return sum(map(len, (
            self.canonical_url,
            self.document_type,
            self.title,
            self.description,
            self.body,
            *self.headings,
            *self.code_blocks,
            *self.tags,
        )))


class IndexStatus(StrEnum):
    """Result of attempting to synchronize one document with search_index."""

    INDEXED = "indexed"
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    SKIPPED = "skipped"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexResult:
    """One document-level outcome for worker telemetry and diagnostics."""

    document_id: int
    status: IndexStatus
    duration_ms: float = 0.0
    indexed_hash: str | None = None
    details: str | None = None

    def __post_init__(self) -> None:
        _positive_id(self.document_id, name="document_id")
        if not isinstance(self.status, IndexStatus):
            raise ValueError("status must be an IndexStatus value")
        if (
            isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, (int, float))
            or not math.isfinite(self.duration_ms)
            or self.duration_ms < 0
        ):
            raise ValueError("duration_ms must be finite and nonnegative")
        if self.indexed_hash is not None and not isinstance(self.indexed_hash, str):
            raise ValueError("indexed_hash must be a string or None")
        if self.details is not None and not isinstance(self.details, str):
            raise ValueError("details must be a string or None")
