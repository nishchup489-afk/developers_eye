
"""Data structures for Developer's Eye content parsers.

These schemas represent extracted content before normalization,
classification, deduplication, and database persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DiscoveredLink:
    """A hyperlink extracted from an HTML page, feed, or API."""

    url: str
    anchor_text: str = ""
    rel: tuple[str, ...] = ()
    nofollow: bool = False


@dataclass(slots=True)
class ParsedDocument:
    """One document extracted from a downloaded resource."""

    url: str

    title: str | None = None
    description: str | None = None
    body: str = ""
    author: str | None = None

    canonical_url_hint: str | None = None
    published_at: datetime | None = None

    headings: tuple[str, ...] = ()
    code_blocks: tuple[str, ...] = ()

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParseResult:
    """Complete result of parsing one fetched resource."""

    source_url: str
    content_type: str

    documents: tuple[ParsedDocument, ...] = ()
    discovered_links: tuple[DiscoveredLink, ...] = ()
