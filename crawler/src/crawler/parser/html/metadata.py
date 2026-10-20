"""Extract document metadata from an already-parsed HTML tree.

No HTTP requests, database writes, or mutation of the BeautifulSoup tree.
Canonical and image URLs are hints, not permission to fetch them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


_WHITESPACE = re.compile(r"\s+")
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


@dataclass(frozen=True, slots=True)
class ExtractedMetadata:
    """Metadata to merge into the parser's ParsedDocument."""

    title: str | None = None
    description: str | None = None
    author: str | None = None
    canonical_url_hint: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _clean_text(value: object, *, max_length: int = 2048) -> str | None:
    """Return compact, bounded text, or None for missing/empty values."""

    if not isinstance(value, str):
        return None
    cleaned = _WHITESPACE.sub(" ", value).strip()
    return cleaned[:max_length] or None


def _collect_meta(soup: BeautifulSoup | Tag) -> dict[str, list[str]]:
    """Index meta tags by name, property, itemprop and http-equiv."""

    values: dict[str, list[str]] = defaultdict(list)

    for tag in soup.find_all("meta"):
        content = _clean_text(tag.get("content"))
        if content is None:
            continue

        for attribute in ("name", "property", "itemprop", "http-equiv"):
            key = _clean_text(tag.get(attribute), max_length=128)
            if key:
                values[key.casefold()].append(content)

    return dict(values)


def _first_meta(
    meta: dict[str, list[str]],
    *keys: str,
    max_length: int = 2048,
) -> str | None:
    for key in keys:
        for value in meta.get(key.casefold(), ()):
            cleaned = _clean_text(value, max_length=max_length)
            if cleaned:
                return cleaned
    return None


def _valid_http_url(value: str) -> bool:
    """Check URL structure only; does not authorize network access."""

    if not value or any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\" for char in value):
        return False

    try:
        parts = urlsplit(value)
        port = parts.port
        hostname = parts.hostname
        username = parts.username
        password = parts.password
    except ValueError:
        return False

    return (
        parts.scheme.lower() in {"http", "https"}
        and bool(parts.netloc)
        and bool(hostname)
        and username is None
        and password is None
        and not parts.netloc.endswith(":")
        and (port is None or port > 0)
    )


def _resolve_url_hint(page_url: str, reference: object) -> str | None:
    """Resolve a URL hint without trusting it as an approved crawl target."""

    if not isinstance(reference, str):
        return None
    reference = reference.strip()
    if not reference or not _valid_http_url(page_url):
        return None
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\" for char in reference):
        return None

    try:
        candidate_reference = urlsplit(reference)
    except ValueError:
        return None

    # Reject malformed absolute references, rather than letting urljoin
    # reinterpret them as relative paths.
    if candidate_reference.scheme and (
        candidate_reference.scheme.lower() not in {"http", "https"}
        or not candidate_reference.netloc
    ):
        return None

    try:
        resolved = urldefrag(urljoin(page_url, reference)).url
    except ValueError:
        return None
    return resolved if _valid_http_url(resolved) else None


def _parse_published_at(value: object) -> datetime | None:
    """Parse dated metadata into an aware UTC datetime when unambiguous."""

    raw = _clean_text(value, max_length=128)
    if raw is None:
        return None

    try:
        if _DATE_ONLY.fullmatch(raw):
            # A source date without time is represented at 00:00 UTC.
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None

    # Do not invent a timezone for timestamps that omit one.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical_link(soup: BeautifulSoup | Tag) -> str | None:
    """Return the first nonempty rel=canonical href, if present."""

    for link in soup.find_all("link", href=True):
        rel = link.get("rel", [])
        tokens = [rel] if isinstance(rel, str) else rel
        if any(isinstance(token, str) and token.casefold() == "canonical" for token in tokens):
            href = _clean_text(link.get("href"))
            if href:
                return href
    return None


def extract_metadata(
    soup: BeautifulSoup | Tag,
    page_url: str,
) -> ExtractedMetadata:
    """Extract title, description, author, dates and useful HTML metadata.

    ``page_url`` is the final fetched URL, used only to resolve relative hints.
    The caller must validate any canonical/image URL before using it elsewhere.
    """

    if not isinstance(soup, Tag):
        raise TypeError("soup must be a BeautifulSoup or Tag instance")
    if not isinstance(page_url, str) or not _valid_http_url(page_url):
        raise ValueError("page_url must be an absolute HTTP(S) URL")

    meta = _collect_meta(soup)

    title_element = soup.find("title")
    title_tag = _clean_text(title_element.get_text(" ", strip=True), max_length=512) if title_element else None
    h1_element = soup.find("h1")
    h1_title = _clean_text(h1_element.get_text(" ", strip=True), max_length=512) if h1_element else None

    title = (
        _first_meta(meta, "og:title", "twitter:title", max_length=512)
        or title_tag
        or h1_title
    )
    description = _first_meta(
        meta,
        "description",
        "og:description",
        "twitter:description",
        max_length=2048,
    )
    author = _first_meta(
        meta, "author", "article:author", "dc.creator", max_length=512
    )

    canonical_hint = _resolve_url_hint(page_url, _canonical_link(soup))
    if canonical_hint is None:
        canonical_hint = _resolve_url_hint(page_url, _first_meta(meta, "og:url"))

    published_at: datetime | None = None
    for key in (
        "article:published_time", "datepublished", "pubdate",
        "publishdate", "publish_date", "dc.date.issued", "dc.date",
    ):
        for value in meta.get(key, ()):
            published_at = _parse_published_at(value)
            if published_at is not None:
                break
        if published_at is not None:
            break

    if published_at is None:
        for time_tag in soup.find_all("time", datetime=True):
            classes = time_tag.get("class", [])
            class_tokens = [classes] if isinstance(classes, str) else classes
            semantic_hint = " ".join(
                [str(time_tag.get("itemprop", "")), *map(str, class_tokens)]
            ).casefold()
            if any(term in semantic_hint for term in ("published", "pubdate", "datepublished")):
                published_at = _parse_published_at(time_tag.get("datetime"))
                if published_at is not None:
                    break

    extra: dict[str, Any] = {}

    html_tag = soup if soup.name == "html" else soup.find("html")
    language = _clean_text(html_tag.get("lang"), max_length=32) if isinstance(html_tag, Tag) else None
    language = language or _first_meta(meta, "content-language", max_length=32)
    if language:
        extra["language"] = language

    site_name = _first_meta(meta, "og:site_name", "application-name", max_length=256)
    if site_name:
        extra["site_name"] = site_name

    content_kind = _first_meta(meta, "og:type", max_length=128)
    if content_kind:
        extra["og_type"] = content_kind

    keywords = _first_meta(meta, "keywords", max_length=2048)
    if keywords:
        extra["keywords"] = [
            token for item in keywords.split(",")
            if (token := _clean_text(item, max_length=100))
        ][:30]

    robots = _first_meta(meta, "robots", max_length=1024)
    if robots:
        extra["robots_directives"] = [
            token for item in robots.split(",")
            if (token := _clean_text(item, max_length=100))
        ][:30]
        extra["robots_directives"] = [v.casefold() for v in extra["robots_directives"]]

    image = _resolve_url_hint(
        page_url, _first_meta(meta, "og:image", "twitter:image")
    )
    if image:
        extra["image_url_hint"] = image

    section = _first_meta(meta, "article:section", max_length=256)
    if section:
        extra["section"] = section

    tags = [
        tag for raw in meta.get("article:tag", ())
        if (tag := _clean_text(raw, max_length=128))
    ][:30]
    if tags:
        extra["article_tags"] = tags

    source_updated = _first_meta(
        meta, "article:modified_time", "datemodified", "last-modified"
    )
    updated_at = _parse_published_at(source_updated)
    if updated_at:
        extra["source_updated_at"] = updated_at.isoformat()

    return ExtractedMetadata(
        title=title,
        description=description,
        author=author,
        canonical_url_hint=canonical_hint,
        published_at=published_at,
        metadata=extra,
    )
