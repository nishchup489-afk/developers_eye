"""Generate stable content fingerprints for Developer's Eye.

Input:  NormalizedDocument from crawler.processing.schemas.
Output:  A 64-character lowercase SHA-256 hexadecimal string.

This module does not fetch, classify, query the database, or deduplicate.
It fingerprints normalized document content, not its URL or crawl metadata.
"""

#{ Alternate hashing option : BLAKE3}

from __future__ import annotations

import hashlib
import json

from crawler.processing.schemas import NormalizedDocument


# Domain separation and versioning prevent accidental reuse of the same
# digest convention for a different payload format in the future.
_FINGERPRINT_PREFIX = b"developers-eye:content:v1\x00"


def _document_payload(document: NormalizedDocument) -> bytes:
    """Serialize relevant content fields in a deterministic, unambiguous way.

    URL, canonical URL, author, publication time, and metadata are deliberately
    excluded: they can change without the page's searchable content changing.

    Classification and tags are also excluded because they're derived from the
    document and may change as classification rules are improved.
    """
    if not isinstance(document, NormalizedDocument):
        raise TypeError("document must be a NormalizedDocument")

    for name in ("title", "description"):
        value = getattr(document, name)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"document.{name} must be str or None")

    if not isinstance(document.body, str):
        raise TypeError("document.body must be a string")

    for name in ("headings", "code_blocks"):
        value = getattr(document, name)
        if not isinstance(value, tuple) or not all(
            isinstance(item, str) for item in value
        ):
            raise TypeError(f"document.{name} must be a tuple of strings")

    payload = {
        "title": document.title or "",
        "description": document.description or "",
        "body": document.body,
        "headings": document.headings,
        "code_blocks": document.code_blocks,
    }

    # JSON disambiguates field boundaries. Sorting keys ensures output isn't
    # dependent on dictionary insertion order. UTF-8 makes bytes consistent.
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def fingerprint_document(document: NormalizedDocument) -> str:
    """Return the SHA-256 hex digest of normalized, searchable content.

    Identical content fields produce identical fingerprints, even when the
    fetched URL or crawl metadata differ. This does not decide whether a
    document is a duplicate; the database writer makes that decision.
    """
    serialized = _document_payload(document)
    return hashlib.sha256(_FINGERPRINT_PREFIX + serialized).hexdigest()


__all__ = ["fingerprint_document"]
