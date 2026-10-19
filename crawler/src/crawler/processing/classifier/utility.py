# Avoid matching malicious lookalike domains such as 'notgithub.com'.
from urllib.parse import urlsplit

from crawler.src.crawler.processing.classifier.patterns import _TOPIC_PATTERNS
from crawler.src.crawler.processing.schemas import NormalizedDocument


def _on_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _metadata_string(metadata: dict, *keys: str) -> str:
    """Return the first nonempty string for any recognized metadata key."""
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _topic_tags(document: NormalizedDocument) -> tuple[str, ...]:
    """Derive a small set of topic tags from reliable, short text fields."""
    metadata = document.metadata if isinstance(document.metadata, dict) else {}
    keywords = metadata.get("keywords", "")

    if isinstance(keywords, (tuple, list)):
        keywords_text = " ".join(str(item) for item in keywords if isinstance(item, str))
    elif isinstance(keywords, str):
        keywords_text = keywords
    else:
        keywords_text = ""

    # Don't scan the entire body: a passing reference should not tag a page.
    searchable = " ".join(
        (document.title or "", document.description or "", keywords_text)
    )
    searchable += " " + urlsplit(document.canonical_url).path.replace("-", " ").replace("_", " ")

    return tuple(
        name
        for name, pattern in _TOPIC_PATTERNS
        if pattern.search(searchable)
    )[:8]

