"""Orchestrate Developer's Eye's content-processing pipeline.

Input:  ParseResult from crawler.parser.schemas.
Output: ProcessingResult from crawler.processing.schemas.

Pipeline for each ParsedDocument:
    normalize -> check noindex / empty content -> classify -> fingerprint
    -> assemble ProcessedDocument (or SkippedDocument).

Pure, synchronous processing: no HTTP, DNS, database I/O, or frontier writes.
The worker handles discovered links independently of processing decisions.
"""

from __future__ import annotations

import re

from crawler.parser.schemas import ParsedDocument, ParseResult
from crawler.processing.classifier.classify import classify_document
from crawler.processing.fingerprint import fingerprint_document
from crawler.processing.normalize.normalize import normalize_document
from crawler.processing.schemas import (
    ProcessedDocument,
    ProcessingResult,
    SkipReason,
    SkippedDocument,
)
from dataclasses import replace
from urllib.parse import urlsplit, unquote

_ROBOTS_SEPARATOR = re.compile(r"[,;\s]+")
_NO_INDEX = frozenset({"noindex", "none"})


def _has_noindex(metadata: dict) -> bool:
    """Read HTML robots directives extracted by html/metadata.py.

    Recognizes `noindex` or `none` in metadata['robots_directives'].
    `nofollow` alone does not prevent indexing. HTTP X-Robots-Tag headers
    must be handled by the Worker or carried into the parser metadata.
    """
    raw = metadata.get("robots_directives", ())

    if isinstance(raw, str):
        values = (raw,)
    elif isinstance(raw, (list, tuple, set, frozenset)):
        values = raw
    else:
        return False

    for value in values:
        if not isinstance(value, str):
            continue
        directives = {
            item.casefold()
            for item in _ROBOTS_SEPARATOR.split(value.strip())
            if item
        }
        if directives & _NO_INDEX:
            return True

    return False



def _fallback_title(
    canonical_url: str,
    headings: tuple[str, ...],
) -> str:
    """Generate a usable title when the HTML title is missing."""

    # STEP 1: Prefer the first meaningful heading.
    for heading in headings:
        if heading.strip():
            return heading.strip()

    # STEP 2: Use the final URL path segment.
    parsed = urlsplit(canonical_url)

    path = parsed.path.rstrip("/")
    slug = unquote(path.rsplit("/", 1)[-1])

    # Remove a common HTML file extension.
    if slug.lower().endswith((".html", ".htm")):
        slug = slug.rsplit(".", 1)[0]

    slug = slug.replace("-", " ").replace("_", " ").strip()

    if slug:
        return slug

    # STEP 3: Root URL without a useful path.
    return parsed.hostname or "Untitled"


def process_document(document: ParsedDocument) -> ProcessedDocument | SkippedDocument:
    """Normalize, filter, classify, and fingerprint one parsed document.

    Expected bad document data is represented as SkippedDocument so a
    single malformed page does not discard other documents in a feed.
    Unexpected programming errors are allowed to surface rather than being
    silently swallowed.
    """
    if not isinstance(document, ParsedDocument):
        raise TypeError("document must be a ParsedDocument")

    # STEP 1: Normalize URL, text, headings, code and canonical identity.
    try:
        normalized = normalize_document(document)
    except ValueError as exc:
        return SkippedDocument(
            url=document.url,
            reason=SkipReason.INVALID_URL,
            details=str(exc),
        )
    except (TypeError, UnicodeError) as exc:
        return SkippedDocument(
            url=document.url,
            reason=SkipReason.PROCESSING_ERROR,
            details=f"Normalization failed: {exc}",
        )

    # STEP 2: Respect HTML noindex. 'nofollow' is not the same directive.
    if _has_noindex(normalized.metadata):
        return SkippedDocument(
            url=normalized.url,
            reason=SkipReason.NOINDEX,
            details="Page contains a robots noindex directive",
        )

    # STEP 3: Don't index empty extracted pages. A code-only page is valid.
    if not normalized.body.strip() and not any(
        block.strip() for block in normalized.code_blocks
    ):
        return SkippedDocument(
            url=normalized.url,
            reason=SkipReason.EMPTY_CONTENT,
            details="No readable body or code content to index",
        )

    # Generate a title for valid, titleless documents.
    if not normalized.title:
        normalized = replace(
            normalized,
            title=_fallback_title(
                normalized.canonical_url,
                normalized.headings,
            ),
            metadata={
                **normalized.metadata,
                "generated_title": True,
            },
        )

    # STEP 4: Classify the type and recognized technology topics.
    # STEP 5: Fingerprint the normalized searchable content.
    try:
        classification = classify_document(normalized)
        content_hash = fingerprint_document(normalized)
    except (TypeError, ValueError, UnicodeError) as exc:
        return SkippedDocument(
            url=normalized.url,
            reason=SkipReason.PROCESSING_ERROR,
            details=f"Classification/fingerprinting failed: {exc}",
        )

    # STEP 6: Assemble the final database-ready schema.
    # The classifier's diagnostic details go into the JSONB metadata.
    metadata = dict(normalized.metadata)
    metadata["classification"] = {
        "confidence": classification.confidence,
        "method": classification.method,
    }

    return ProcessedDocument(
        url=normalized.url,
        canonical_url=normalized.canonical_url,
        document_type=classification.document_type,
        title=normalized.title,
        description=normalized.description,
        body=normalized.body,
        author=normalized.author,
        content_hash=content_hash,
        published_at=normalized.published_at,
        headings=normalized.headings,
        code_blocks=normalized.code_blocks,
        tags=classification.tags,
        metadata=metadata,
    )


# [TODO : add x-robot-check and other metadata check]

def process(parse_result: ParseResult) -> ProcessingResult:
    """Process every document from one parsed response.

    A ParseResult can contain multiple documents (e.g. future RSS/JSON).
    Discovered links are deliberately not processed or enqueued here.
    """
    if not isinstance(parse_result, ParseResult):
        raise TypeError("parse_result must be a ParseResult")

    accepted: list[ProcessedDocument] = []
    skipped: list[SkippedDocument] = []

    for document in parse_result.documents:
        result = process_document(document)

        if isinstance(result, ProcessedDocument):
            accepted.append(result)
        else:
            skipped.append(result)

    return ProcessingResult(
        source_url=parse_result.source_url,
        documents=tuple(accepted),
        skipped=tuple(skipped),
    )


__all__ = ["process_document", "process"]
