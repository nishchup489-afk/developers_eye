"""Parse bounded RSS 2.0 and Atom 1.0 feeds into document records."""
from xml.etree.ElementTree import ParseError, tostring

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

from crawler.frontier.urls import normalize_url
from crawler.parser.errors import MalformedContentError
from crawler.parser.schemas import DiscoveredLink, ParsedDocument, ParseResult
from crawler.parser.structured import parse_record_date, readable_markup, resolve_record_url

MAX_FEED_BYTES = 2_000_000
MAX_FEED_ENTRIES = 1_000
ATOM = "{http://www.w3.org/2005/Atom}"
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
CREATOR = "{http://purl.org/dc/elements/1.1/}creator"


def _text(element) -> str:
    return "" if element is None else "".join(element.itertext()).strip()


def _markup(element, *, atom: bool = False) -> str:
    if element is None:
        return ""
    if atom and element.get("type", "text") == "text":
        return _text(element)
    value = (element.text or "") + "".join(tostring(child, encoding="unicode") for child in element)
    return readable_markup(value)


def _base(element, parent: str) -> str:
    value = element.get(XML_BASE)
    if value is None:
        return parent
    resolved = resolve_record_url(value, parent)
    if resolved is None:
        raise MalformedContentError("Invalid feed xml:base")
    return resolved


def _atom_link(element, namespace: str, base: str, relation: str) -> str | None:
    for link in element.findall(namespace + "link"):
        if link.get("rel", "alternate") != relation:
            continue
        if relation == "alternate" and link.get("type", "text/html") not in {"text/html", "application/xhtml+xml"}:
            continue
        resolved = resolve_record_url(link.get("href"), _base(link, base))
        if resolved is not None:
            return resolved
    return None


def parse_feed(*, url: str, content: bytes, content_type: str) -> ParseResult:
    normalize_url(url)
    if not isinstance(content, bytes):
        raise TypeError("Feed content must be bytes")
    if not content or len(content) > MAX_FEED_BYTES:
        raise MalformedContentError("Empty or oversized feed")
    try:
        root = fromstring(content, forbid_dtd=True)
    except (ParseError, DefusedXmlException) as exc:
        raise MalformedContentError("Invalid or unsafe feed XML") from exc
    base = _base(root, url)
    if root.tag == "rss":
        container = root.find("channel")
        if container is None:
            raise MalformedContentError("RSS feed has no channel")
        namespace, entry_tag, format_name = "", "item", "rss"
        base = _base(container, base)
    elif root.tag in {ATOM + "feed", "feed"}:
        container = root
        namespace = ATOM if root.tag.startswith(ATOM) else ""
        entry_tag, format_name = namespace + "entry", "atom"
    else:
        raise MalformedContentError("Expected RSS 2.0 or Atom feed")
    entries = container.findall(entry_tag)
    if len(entries) > MAX_FEED_ENTRIES:
        raise MalformedContentError("Too many feed entries")
    documents, links, seen = [], [], set()
    for entry in entries:
        entry_base = _base(entry, base)
        if format_name == "rss":
            link = entry.find("link")
            entry_url = resolve_record_url(_text(link), _base(link, entry_base) if link is not None else entry_base)
            guid = entry.find("guid")
            if entry_url is None and guid is not None and guid.get("isPermaLink", "true").casefold() == "true":
                entry_url = resolve_record_url(_text(guid), "")
            body = entry.find(CONTENT)
            if body is None:
                body = entry.find("description")
            author = _text(entry.find("author")) or _text(entry.find(CREATOR))
            published = _text(entry.find("pubDate"))
        else:
            entry_url = _atom_link(entry, namespace, entry_base, "alternate")
            if entry_url is None:
                identity = _text(entry.find(namespace + "id"))
                # Atom IDs can be opaque URNs; they are not relative page links.
                entry_url = resolve_record_url(identity, "")
            body = entry.find(namespace + "content")
            if body is None or body.get("src"):
                body = entry.find(namespace + "summary")
            author = _text(entry.find(namespace + "author/" + namespace + "name")) or _text(container.find(namespace + "author/" + namespace + "name"))
            published = _text(entry.find(namespace + "published")) or _text(entry.find(namespace + "updated"))
        if entry_url is None or entry_url in seen:
            continue
        seen.add(entry_url)
        summary = entry.find("description" if format_name == "rss" else namespace + "summary")
        documents.append(ParsedDocument(url=entry_url,
            title=_markup(entry.find(namespace + "title"), atom=format_name == "atom") or None,
            body=_markup(body, atom=format_name == "atom"), description=_markup(summary, atom=format_name == "atom") or None, author=author or None,
            published_at=parse_record_date(published),
            metadata={"ingestion_format": format_name, "feed_url": url}))
        links.append(DiscoveredLink(url=entry_url))
    next_url = _atom_link(container, namespace if format_name == "atom" else ATOM, base, "next")
    if next_url:
        links.append(DiscoveredLink(url=next_url, kind="rss"))
    return ParseResult(source_url=url, content_type=content_type, documents=tuple(documents), discovered_links=tuple(links))
