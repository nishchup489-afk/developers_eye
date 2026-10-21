"""Parse XML sitemaps without fetching URLs or writing to the database."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
from io import BytesIO
from urllib.parse import urlsplit
from xml.etree.ElementTree import ParseError

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

from crawler.parser.errors import MalformedContentError
from crawler.frontier.urls import normalize_url
from crawler.parser.schemas import DiscoveredLink, ParseResult

MAX_XML_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 50_000
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"


@dataclass(frozen=True, slots=True)
class SitemapResult:
    page_urls: tuple[str, ...] = ()
    sitemap_urls: tuple[str, ...] = ()


def _name(tag: str) -> str:
    """Ignore optional XML namespace, e.g. {namespace}urlset."""
    return tag.rsplit("}", 1)[-1]


def _http_url(value: str) -> bool:
    """Basic syntax check only; host/scope/robots checks happen later."""
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c == "\\" for c in value):
        return False
    try:
        parts = urlsplit(value)
        return (
            parts.scheme.lower() in {"http", "https"}
            and bool(parts.netloc)
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and parts.port != 0
            and not parts.netloc.endswith(":")
        )
    except ValueError:
        return False


def parse_sitemap(content: bytes) -> SitemapResult:
    """Return page URLs from <urlset> or child sitemap URLs from <sitemapindex>."""
    if not isinstance(content, bytes):
        raise TypeError("XML content must be bytes")
    if not content or len(content) > MAX_XML_BYTES:
        raise MalformedContentError("Empty or oversized sitemap XML")

    if content.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=BytesIO(content)) as stream:
                content = stream.read(MAX_XML_BYTES + 1)
        except (OSError, EOFError) as exc:
            raise MalformedContentError("Invalid gzip sitemap") from exc
        if len(content) > MAX_XML_BYTES:
            raise MalformedContentError("Decompressed sitemap exceeds XML limit")

    try:
        root = fromstring(content, forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise MalformedContentError("Invalid or unsafe sitemap XML") from exc

    kind = _name(root.tag)
    namespace = root.tag.rsplit("}", 1)[0] + "}" if root.tag.startswith("{") else ""
    if namespace not in {"", "{" + SITEMAP_NAMESPACE + "}"} or kind not in {"urlset", "sitemapindex"}:
        raise MalformedContentError(f"Unsupported sitemap root: {kind}")

    entry_name = "url" if kind == "urlset" else "sitemap"
    urls: dict[str, None] = {}
    entries = 0

    for entry in root:
        if entry.tag != namespace + entry_name:
            continue
        entries += 1
        if entries > MAX_ENTRIES:
            raise MalformedContentError("Too many sitemap entries")

        loc = entry.find(namespace + "loc")
        url = (loc.text or "").strip() if loc is not None else ""

        if url and _http_url(url):
            urls[url] = None

    if kind == "urlset":
        return SitemapResult(page_urls=tuple(urls))
    return SitemapResult(sitemap_urls=tuple(urls))


def extract_robots_sitemaps(raw: str) -> tuple[str, ...]:
    """Read at most 100 distinct, absolute Sitemap declarations from robots.txt."""
    urls: dict[str, None] = {}
    for line in raw.splitlines():
        name, separator, value = line.partition("#")[0].partition(":")
        if separator and name.strip().casefold() == "sitemap":
            try:
                urls[normalize_url(value.strip())] = None
            except ValueError:
                continue
            if len(urls) >= 100:
                break
    return tuple(urls)


def parse_sitemap_resource(*, url: str, content: bytes, content_type: str) -> ParseResult:
    result = parse_sitemap(content)
    return ParseResult(
        source_url=url, content_type=content_type,
        discovered_links=tuple(
            [DiscoveredLink(url=value) for value in result.page_urls]
            + [DiscoveredLink(url=value, kind="sitemap") for value in result.sitemap_urls]
        ),
    )
