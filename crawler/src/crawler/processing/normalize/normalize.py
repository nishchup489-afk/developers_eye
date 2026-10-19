"""Normalize parsed documents for Developer's Eye content processing.

Input:  ParsedDocument from crawler.parser.schemas.
Output: NormalizedDocument from crawler.processing.schemas.

This module only transforms already-parsed data. It never fetches URLs,
performs DNS lookups, checks crawling permissions, or writes to a database.

Canonical links are untrusted hints. This MVP accepts a hint only when it
resolves to the same hostname as the fetched page and does not downgrade HTTPS.
"""

from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from crawler.frontier.urls import normalize_url
from crawler.parser.schemas import ParsedDocument
from crawler.processing.schemas import NormalizedDocument
from crawler.src.crawler.processing.normalize.utility import _canonical_url, _clean_body, _clean_code, _clean_short_text, _validate_source_url






def normalize_document(document: ParsedDocument) -> NormalizedDocument:
    """Convert a parsed document into a clean document for classification.

    Does not mutate the input. Empty content and noindex decisions are the
    responsibility of the processor, not the normalizer.
    """
    if not isinstance(document, ParsedDocument):
        raise TypeError("document must be a ParsedDocument")

    fetched_url = _validate_source_url(document.url)
    canonical_url = _canonical_url(fetched_url, document.canonical_url_hint)

    if not isinstance(document.headings, (tuple, list)):
        raise TypeError("document.headings must be a tuple or list")
    if not isinstance(document.code_blocks, (tuple, list)):
        raise TypeError("document.code_blocks must be a tuple or list")
    if not isinstance(document.metadata, dict):
        raise TypeError("document.metadata must be a dictionary")

    code_blocks = tuple(
        cleaned
        for code in document.code_blocks
        if (cleaned := _clean_code(code)).strip()
    )
    headings = tuple(
        cleaned
        for heading in document.headings
        if (cleaned := _clean_short_text(heading)) is not None
    )

    return NormalizedDocument(
        url=fetched_url,
        canonical_url=canonical_url,
        title=_clean_short_text(document.title),
        description=_clean_short_text(document.description),
        body=_clean_body(document.body, code_blocks),
        author=_clean_short_text(document.author),
        published_at=document.published_at,
        headings=headings,
        code_blocks=code_blocks,
        metadata=deepcopy(document.metadata),
    )


__all__ = ["normalize_document"]

