"""Public search: FTS candidates from search_index, shaped for the frontend.

Ranking comes from ``get_full_text_search``. This module only loads the
matching available documents, maps each to a public category, and builds a
plain-text snippet with ``ts_headline``.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Document
from backend.schema.search import SearchCategory, SearchResultOut
from backend.search.retrieval.fts import get_full_text_search

# Over-fetch so a category filter, applied after mapping, still fills a page.
CANDIDATE_LIMIT = 100
SNIPPET_SOURCE_CHARS = 5000
_HEADLINE_OPTIONS = 'StartSel="",StopSel="",MaxWords=35,MinWords=15,ShortWord=2'

_HOST_CATEGORIES: tuple[tuple[str, SearchCategory], ...] = (
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

_TYPE_CATEGORIES: dict[str, SearchCategory] = {
    "documentation": "docs",
    "tutorial": "articles",
    "blog": "articles",
    "question": "stackoverflow",
    "issue": "github",
    "repository": "github",
    "event": "events",
}


def categorize(url: str, document_type: str) -> SearchCategory:
    """Known platforms win over the classifier's document type."""
    host = (urlsplit(url).hostname or "").lower()
    for domain, category in _HOST_CATEGORIES:
        if host == domain or host.endswith("." + domain):
            return category
    return _TYPE_CATEGORIES.get(document_type, "articles")


def _tags(metadata: object) -> list[str]:
    tags = metadata.get("tags") if isinstance(metadata, dict) else None
    if not isinstance(tags, list):
        return []
    return [tag for tag in tags if isinstance(tag, str) and tag][:8]


async def search_documents(
    session: AsyncSession,
    query: str,
    *,
    category: SearchCategory | None = None,
    limit: int = 20,
) -> list[SearchResultOut]:
    hits = await get_full_text_search(query, session, limit=CANDIDATE_LIMIT)
    if not hits:
        return []
    scores = {hit["document_id"]: hit["search_rank"] + hit["code_rank"] for hit in hits}

    text_source = func.concat_ws(
        " ", Document.description, func.left(Document.body, SNIPPET_SOURCE_CHARS)
    )
    snippet = func.ts_headline(
        "english",
        text_source,
        func.websearch_to_tsquery("english", query),
        literal(_HEADLINE_OPTIONS),
    ).label("snippet")
    rows = await session.execute(
        select(
            Document.id,
            Document.canonical_url,
            Document.document_type,
            Document.title,
            Document.description,
            Document.metadata_,
            snippet,
        ).where(Document.id.in_(scores), Document.is_available.is_(True))
    )

    # Keep the retriever's order: score desc, then document id.
    order = {document_id: i for i, document_id in enumerate(scores)}
    ranked: list[tuple[int, SearchResultOut]] = []
    for row in rows:
        url = row.canonical_url
        if urlsplit(url).scheme not in ("http", "https"):
            continue
        source = categorize(url, row.document_type)
        if category is not None and source != category:
            continue
        text = " ".join((row.snippet or row.description or "").split())
        ranked.append((
            order[row.id],
            SearchResultOut(
                title=row.title,
                source=source,
                url=url,
                snippet=text,
                score=round(scores[row.id], 6),
                tags=_tags(row.metadata_),
                type=row.document_type,
            ),
        ))

    ranked.sort(key=lambda item: item[0])
    return [result for _, result in ranked[:limit]]
