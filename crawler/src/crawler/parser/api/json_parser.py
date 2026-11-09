"""Map bounded public JSON responses into the shared document contract."""
from dataclasses import dataclass, field
import json
import math
from typing import Any

from crawler.frontier.urls import normalize_url
from crawler.parser.errors import MalformedContentError
from crawler.parser.schemas import DiscoveredLink, ParsedDocument, ParseResult
from crawler.parser.structured import parse_record_date, readable_markup, resolve_record_url

MAX_JSON_BYTES = 2_000_000
MAX_JSON_ENTRIES = 1_000
DEFAULT_FIELDS = {name: name for name in ("url", "title", "body", "description", "author", "published_at")}


def _path(value: object, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 256 or (not value and not empty) or (value and any(not part for part in value.split("."))):
        raise ValueError("API field paths must be nonempty dotted strings of at most 256 characters")
    return value


def _lookup(value: Any, path: str) -> Any:
    if not path:
        return value
    for key in path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isascii() and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return None
    return value


@dataclass(frozen=True, slots=True)
class ApiMapping:
    items_path: str | None = None
    next_path: str | None = None
    fields: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_FIELDS))
    body_format: str = "text"
    metadata_fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, options: dict | None) -> "ApiMapping":
        options = {} if options is None else options
        if not isinstance(options, dict) or set(options) - {"items_path", "next_path", "fields", "body_format", "metadata_fields"}:
            raise ValueError("API config supports items_path, next_path, fields, body_format and metadata_fields")
        items = _path(options["items_path"], empty=True) if "items_path" in options else None
        next_path = _path(options["next_path"]) if "next_path" in options else None
        fields = options.get("fields", {})
        if not isinstance(fields, dict) or set(fields) - DEFAULT_FIELDS.keys():
            raise ValueError("Unknown API document field mapping")
        fields = {**DEFAULT_FIELDS, **{name: _path(value) for name, value in fields.items()}}
        body_format = options.get("body_format", "text")
        if not isinstance(body_format, str) or body_format not in {"text", "html"}:
            raise ValueError("API body_format must be text or html")
        extra = options.get("metadata_fields", {})
        if (not isinstance(extra, dict) or len(extra) > 20
                or any(not isinstance(k, str) or not k or len(k) > 64 or k in {"ingestion_format", "api_url"} for k in extra)):
            raise ValueError("API metadata_fields must map up to 20 names to field paths")
        extra = {name: _path(value) for name, value in extra.items()}
        return cls(items, next_path, fields, body_format, extra)


def _record_metadata(record: dict, paths: dict[str, str]) -> dict[str, Any]:
    """Copy small scalar values (license, score, ids, tags) into metadata."""
    result = {}
    for name, path in paths.items():
        value = _lookup(record, path)
        if isinstance(value, str) and len(value) <= 1000:
            result[name] = value
        elif isinstance(value, (bool, int, float)) and not (isinstance(value, float) and not math.isfinite(value)):
            result[name] = value
        elif isinstance(value, list) and len(value) <= 50 and all(isinstance(v, str) and len(v) <= 200 for v in value):
            result[name] = list(value)
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON number exceeds finite float range")
    return number


def parse_json_api(*, url: str, content: bytes, content_type: str,
                   options: dict | None = None) -> ParseResult:
    normalize_url(url)
    mapping = ApiMapping.from_config(options)
    if not isinstance(content, bytes):
        raise TypeError("JSON content must be bytes")
    if not content or len(content) > MAX_JSON_BYTES:
        raise MalformedContentError("Empty or oversized JSON response")
    try:
        payload = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_object,
            parse_constant=_reject_constant, parse_float=_finite_float)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise MalformedContentError("Invalid JSON response") from exc
    if mapping.items_path is not None:
        records = _lookup(payload, mapping.items_path)
    elif isinstance(payload, dict) and "items" in payload:
        records = payload["items"]
    else:
        records = payload
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise MalformedContentError("API items path must resolve to an object or array")
    if len(records) > MAX_JSON_ENTRIES:
        raise MalformedContentError("Too many API records")
    documents, links, seen = [], [], set()
    for record in records:
        if not isinstance(record, dict):
            continue
        values = {name: _lookup(record, path) for name, path in mapping.fields.items()}
        record_url = resolve_record_url(values["url"], url)
        if record_url is None or record_url in seen:
            continue
        seen.add(record_url)
        def text(name):
            value = values[name]
            return value.strip() if isinstance(value, str) else ""
        body, description = text("body"), text("description")
        if mapping.body_format == "html":
            body, description = readable_markup(body), readable_markup(description)
        documents.append(ParsedDocument(url=record_url, title=text("title") or None,
            body=body, description=description or None, author=text("author") or None,
            published_at=parse_record_date(values["published_at"]),
            metadata={**_record_metadata(record, mapping.metadata_fields),
                      "ingestion_format": "json_api", "api_url": url}))
        links.append(DiscoveredLink(url=record_url))
    next_url = resolve_record_url(_lookup(payload, mapping.next_path), url) if mapping.next_path else None
    if next_url:
        links.append(DiscoveredLink(url=next_url, kind="api"))
    return ParseResult(source_url=url, content_type=content_type,
        documents=tuple(documents), discovered_links=tuple(links))
