"""Result categories. The indexer stores them, so filters run inside retrieval."""

from __future__ import annotations

from urllib.parse import urlsplit

from backend.schema.search import SearchCategory, SearchFilter

# "discussions" is a filter over two categories, not a category of its own.
FILTER_CATEGORIES: dict[str, tuple[str, ...]] = {"discussions": ("stackoverflow", "reddit")}


def categories_for_filter(filter_: SearchFilter | None) -> tuple[str, ...] | None:
    """The stored categories a filter matches; None means no restriction."""
    if filter_ is None:
        return None
    return FILTER_CATEGORIES.get(filter_, (filter_,))


def categorize(url: str, document_type: str) -> SearchCategory:
    """Assign the existing frontend's supported source category."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return "articles"

    platform_categories: tuple[tuple[str, SearchCategory], ...] = (
        ("github.com", "github"),
        ("gitlab.com", "github"),
        ("stackoverflow.com", "stackoverflow"),
        ("stackexchange.com", "stackoverflow"),
        ("reddit.com", "reddit"),
        ("leetcode.com", "practice"),
        ("hackerrank.com", "practice"),
        ("exercism.org", "practice"),
        ("codewars.com", "practice"),
    )
    for domain, category in platform_categories:
        if host == domain or host.endswith("." + domain):
            return category
    if host == "fastapi.tiangolo.com":
        return "docs"
    by_type: dict[str, SearchCategory] = {
        "documentation": "docs",
        "tutorial": "articles",
        "blog": "articles",
        "question": "stackoverflow",
        "issue": "github",
        "repository": "github",
        "event": "events",
    }
    return by_type.get(document_type, "articles")
