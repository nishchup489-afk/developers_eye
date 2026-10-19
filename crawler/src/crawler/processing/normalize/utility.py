import unicodedata
from urllib.parse import urljoin, urlsplit

from crawler.src.crawler.frontier.urls import normalize_url
from crawler.src.crawler.processing.normalize.helper import _CONTROL_CHARACTERS, _EXCESS_NEWLINES, _HORIZONTAL_WHITESPACE, _WHITESPACE


def _normalize_unicode(value: str) -> str:
    """Normalize Unicode/newlines and remove non-text control characters."""
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARACTERS.sub(" ", value)


def _clean_short_text(value: str | None) -> str | None:
    """Collapse whitespace in a title, description, or author field."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("text fields must contain str or None")

    cleaned = _WHITESPACE.sub(" ", _normalize_unicode(value)).strip()
    return cleaned or None


def _clean_code(value: str) -> str:
    """Preserve code indentation, tabs, and internal line breaks."""
    if not isinstance(value, str):
        raise TypeError("code blocks must contain strings")
    return _normalize_unicode(value).strip("\n")


def _clean_prose_fragment(value: str) -> str:
    """Clean prose while keeping paragraph/line boundaries."""
    lines = (
        _HORIZONTAL_WHITESPACE.sub(" ", line).strip()
        for line in value.split("\n")
    )
    return _EXCESS_NEWLINES.sub("\n\n", "\n".join(lines))


def _clean_body(value: str, code_blocks: tuple[str, ...]) -> str:
    """Normalize prose without changing embedded <pre> code indentation.

    The HTML extractor includes code blocks in both body and code_blocks.
    Protect those exact spans before collapsing whitespace in surrounding
    prose. If a code block is not found, only the matching step is skipped.
    """
    if not isinstance(value, str):
        raise TypeError("document.body must be a string")

    body = _normalize_unicode(value)
    chunks: list[str] = []
    cursor = 0

    for block in code_blocks:
        if not block:
            continue
        position = body.find(block, cursor)
        if position < 0:
            continue

        chunks.append(_clean_prose_fragment(body[cursor:position]))
        chunks.append(block)
        cursor = position + len(block)

    chunks.append(_clean_prose_fragment(body[cursor:]))
    cleaned = "".join(chunks).strip("\n")
    return cleaned if cleaned.strip() else ""


def _validate_source_url(value: str) -> str:
    """Normalize a fetched URL; do not make any network authorization claim."""
    if not isinstance(value, str) or not value:
        raise ValueError("document.url must be a nonempty HTTP(S) URL")

    # Reject URLs that permissive parsers might silently reinterpret.
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
           for char in value):
        raise ValueError("document.url contains invalid characters")

    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ValueError("document.url is malformed") from exc

    if (parts.scheme.lower() not in {"http", "https"}
            or not parts.netloc or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.netloc.endswith(":") or port == 0):
        raise ValueError("document.url must be an absolute HTTP(S) URL")

    # Reuse the exact canonicalization rules used by the Frontier.
    return normalize_url(value)


def _canonical_url(fetched_url: str, hint: str | None) -> str:
    """Choose a same-host canonical hint, otherwise keep fetched_url."""
    if not isinstance(hint, str) or not hint.strip():
        return fetched_url

    hint = hint.strip()
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 or char == "\\"
           for char in hint):
        return fetched_url

    try:
        reference = urlsplit(hint)
        if reference.scheme and (
            reference.scheme.lower() not in {"http", "https"}
            or not reference.netloc
        ):
            return fetched_url

        candidate = _validate_source_url(urljoin(fetched_url, hint))
        current = urlsplit(fetched_url)
        proposed = urlsplit(candidate)
    except (TypeError, ValueError):
        return fetched_url

    # A canonical URL is a storage identity hint, NOT permission to crawl.
    if proposed.hostname != current.hostname:
        return fetched_url
    if current.scheme.lower() == "https" and proposed.scheme.lower() != "https":
        return fetched_url

    return candidate

