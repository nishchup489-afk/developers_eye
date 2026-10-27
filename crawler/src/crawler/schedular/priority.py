
from urllib.parse import urlsplit, unquote


VALID_KINDS = frozenset({"page", "sitemap", "api", "rss"})

REFERENCE_SEGMENTS = frozenset({
    "api",
    "reference",
    "references",
    "ref",
    "library",
    "stdlib",
})

GUIDE_SEGMENTS = frozenset({
    "guide",
    "guides",
    "tutorial",
    "tutorials",
    "howto",
    "learn",
})


def calculate_priority(
    url: str,
    *,
    kind: str = "page",
    is_seed: bool = False,
) -> int:
    """Calculate deterministic crawl priority for a validated URL."""

    if kind not in VALID_KINDS:
        raise ValueError(f"Unsupported target kind: {kind}")

    if not isinstance(url, str) or any(
        char.isspace() or ord(char) < 32 for char in url
    ):
        raise ValueError("Invalid URL")

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ValueError("Malformed URL") from exc

    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError("URL must be absolute HTTP(S)")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL must not contain credentials")

    # Resource types and initial discovery
    if is_seed:
        return 100

    if kind == "sitemap":
        return 90

    if kind == "api":
        return 85

    if kind == "rss":
        return 60

    # Path-based classification
    segments = {
        unquote(segment).casefold()
        for segment in parsed.path.split("/")
        if segment
    }

    if segments & REFERENCE_SEGMENTS:
        return 80

    if segments & GUIDE_SEGMENTS:
        return 70

    return 50
