
"""HTML-only entry point for Developer's Eye's content parser.

Consumes already-fetched bytes. No HTTP requests, policy checks, database
writes, or document classification happen here.

Structured resource parsers are selected separately by the worker.
"""

from __future__ import annotations

import codecs
from email.message import Message
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, FeatureNotFound

from crawler.parser.errors import (
    ContentDecodeError,
    MalformedContentError,
    ParserError,
    UnsupportedContentTypeError,
)
from crawler.parser.html.extractor import extract_main_content
from crawler.parser.html.links import extract_links
from crawler.parser.html.metadata import extract_metadata
from crawler.parser.schemas import ParsedDocument, ParseResult


_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})


def _validate_page_url(url: str) -> None:
    """Check source URL structure without authorizing network access."""
    if not isinstance(url, str) or not url or any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
        for char in url
    ):
        raise ParserError("url must be a valid absolute HTTP(S) URL")

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ParserError("Malformed source URL") from exc

    if (
        parts.scheme.lower() not in ("http", "https")
        or not parts.netloc
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.netloc.endswith(":")
        or port == 0
    ):
        raise ParserError(
            "url must be an absolute HTTP(S) URL without credentials"
        )


def _parse_content_type(value: str | None) -> tuple[str, str | None]:
    """Read MIME type and optional charset from Content-Type."""
    if not isinstance(value, str) or not value.strip():
        raise UnsupportedContentTypeError("Missing Content-Type header")

    header = Message()
    header["Content-Type"] = value

    media_type = value.partition(";")[0].strip().casefold()

    if media_type not in _HTML_TYPES:
        raise UnsupportedContentTypeError(
            f"HTML parser does not support content type {media_type!r}"
        )

    charset = header.get_param("charset", header="Content-Type")

    if charset is not None:
        if not isinstance(charset, str) or not charset.strip():
            raise ContentDecodeError("Invalid declared HTML charset")

        charset = charset.strip()

        try:
            codecs.lookup(charset)
        except LookupError as exc:
            raise ContentDecodeError(
                f"Unknown HTML charset: {charset!r}"
            ) from exc

    return media_type, charset


def parse(
    *,
    url: str,
    content: bytes,
    content_type: str | None,
) -> ParseResult:
    """Parse one fetched HTML page into documents and discovered links.

    The caller should supply a successful, nonempty FetchResult body.
    All discovered links remain untrusted until validated by the frontier
    and crawler policies.
    """

    # STEP 1: Validate inputs.
    _validate_page_url(url)
    media_type, charset = _parse_content_type(content_type)

    if not isinstance(content, bytes):
        raise TypeError("content must be bytes from FetchResult.body")

    if not content.strip():
        raise MalformedContentError("The HTML response body is empty")

    # STEP 2: Build the HTML tree.
    try:
        soup = BeautifulSoup(
            content,
            "lxml",
            from_encoding=charset,
        )
    except (FeatureNotFound, UnicodeError, ValueError) as exc:
        raise MalformedContentError("HTML parsing failed") from exc

    # STEP 3: Delegate content extraction.
    extracted = extract_main_content(soup)

    # STEP 4: Extract metadata.
    metadata = extract_metadata(soup, page_url=url)

    # STEP 5: Discover links.
    links = extract_links(soup, page_url=url)

    # STEP 6: Assemble the document.
    document = ParsedDocument(
        url=url,
        title=metadata.title,
        description=metadata.description,
        body=extracted.body,
        author=metadata.author,
        canonical_url_hint=metadata.canonical_url_hint,
        published_at=metadata.published_at,
        headings=extracted.headings,
        code_blocks=extracted.code_blocks,
        metadata=metadata.metadata,
    )

    # STEP 7: Return structured parser output.
    return ParseResult(
        source_url=url,
        content_type=media_type,
        documents=(document,),
        discovered_links=links,
    )
