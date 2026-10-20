
"""Schemas for Developer's Eye Content Processing Pipeline.

Pipeline:
    ParsedDocument
        -> Normalization
        -> Classification
        -> Content Fingerprinting
        -> ProcessedDocument

This module only defines data structures.
No HTTP requests, database queries, or content processing logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


# ============================================================
# 1. DOCUMENT TYPES
# ============================================================

class DocumentType(StrEnum):
    """Supported categories of developer content."""

    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    BLOG = "blog"
    QUESTION = "question"
    DISCUSSION = "discussion"
    ISSUE = "issue"
    REPOSITORY = "repository"
    EVENT = "event"
    OTHER = "other"


    # will add more after testing on V2 or MVP -> MLP


# ============================================================
# 2. SKIP REASONS
# ============================================================

class SkipReason(StrEnum):
    """Why a document was rejected during processing."""

    EMPTY_CONTENT = "empty_content"
    NOINDEX = "noindex"
    INVALID_URL = "invalid_url"
    PROCESSING_ERROR = "processing_error"


# ============================================================
# 3. NORMALIZED DOCUMENT
# ============================================================

@dataclass(slots=True)
class NormalizedDocument:
    """Document after text and URL normalization.

    Input:
        ParsedDocument from parser.schemas

    Produced by:
        normalizer.py

    Responsibilities:
        - Clean whitespace and Unicode text
        - Normalize document fields
        - Validate canonical URL hints
        - Preserve headings and code blocks
        - Prepare content for classification
    """

    url: str
    canonical_url: str

    body: str

    title: str | None = None
    description: str | None = None
    author: str | None = None

    published_at: datetime | None = None

    headings: tuple[str, ...] = ()
    code_blocks: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# 4. CLASSIFICATION RESULT
# ============================================================

@dataclass(slots=True)
class ClassificationResult:
    """Result of classifying a normalized document.

    Produced by:
        classifier.py

    Classification can use:
        - URL patterns
        - Source information
        - Page metadata
        - Title and body content

    Confidence is between 0.0 and 1.0.
    """

    document_type: DocumentType

    confidence: float = 0.0

    tags: tuple[str, ...] = ()

    method: str = "rules"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )


# ============================================================
# 5. PROCESSED DOCUMENT
# ============================================================

@dataclass(slots=True)
class ProcessedDocument:
    """Final document ready for database persistence.

    Produced after:
        Normalization
        Classification
        Content fingerprinting

    Database writer will later map this schema
    into the backend Document model.

    content_hash:
        SHA-256 fingerprint of normalized content.

    Duplicate detection against existing documents
    happens separately using the fingerprint.
    """

    url: str
    canonical_url: str

    document_type: DocumentType

    title: str | None
    description: str | None

    body: str

    author: str | None

    content_hash: str

    published_at: datetime | None = None

    headings: tuple[str, ...] = ()
    code_blocks: tuple[str, ...] = ()

    tags: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# 6. SKIPPED DOCUMENT
# ============================================================

@dataclass(slots=True)
class SkippedDocument:
    """A document that cannot proceed through processing."""

    url: str

    reason: SkipReason

    details: str | None = None


# ============================================================
# 7. PROCESSING RESULT
# ============================================================

@dataclass(slots=True)
class ProcessingResult:
    """Final result returned by the processing pipeline.

    A single ParseResult can contain multiple documents,
    particularly when RSS/Atom and API parsers are added.

    Accepted documents are returned in documents.
    Rejected documents are returned in skipped.

    Discovered links are handled separately by the Worker.
    """

    source_url: str

    documents: tuple[ProcessedDocument, ...] = ()

    skipped: tuple[SkippedDocument, ...] = ()
