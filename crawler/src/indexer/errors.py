"""Application-level exceptions for Developer's Eye indexing.

The indexer deliberately preserves the underlying SQLAlchemy/asyncpg error
through exception chaining when a database operation fails.
"""

from __future__ import annotations


class IndexerError(Exception):
    """Base class for expected indexer-level failures."""


class IndexerConfigError(IndexerError, ValueError):
    """An environment variable or indexer setting is invalid."""


class IndexDocumentError(IndexerError, ValueError):
    """A stored document cannot be converted into a valid index document."""

    def __init__(self, message: str, *, document_id: int | None = None) -> None:
        self.document_id = document_id
        prefix = f"document_id={document_id}: " if document_id is not None else ""
        super().__init__(prefix + message)


class IndexDocumentTooLargeError(IndexDocumentError):
    """Indexable text exceeds the configured limit; never silently truncate."""


class StaleIndexSourceError(IndexerError):
    """The source document changed after selection; reload and retry it."""


class IndexWriteError(IndexerError):
    """Index persistence failed; retain the original exception as __cause__."""
