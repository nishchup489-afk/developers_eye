
from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate

from crawler.frontier.urls import normalize_url
from crawler.frontier.repository import enqueue_targets
from crawler.frontier.scope import CrawlScope
from crawler.policy_and_politeness.host_policy import is_allowed_host
from urllib.parse import urlsplit, urlunsplit

from .registry import get_enabled_sources


def build_initial_target(source: Source) -> CrawlTargetCreate:
    """Convert one website source into an initial crawl target."""

    if source.kind != "website":
        raise ValueError("Unsupported source kind")

    target = {
        "source_id": source.id,
        "fetch_url": source.base_url,
        "normalized_url": normalize_url(source.base_url),
        "kind": "page",
        "priority": source.config.get("priority", 0),
        "discovered_from_id": None,
    }

    return CrawlTargetCreate.model_validate(target)


def build_initial_targets(source: Source) -> list[CrawlTargetCreate]:
    """Build one page seed and bounded sitemap candidates without network I/O."""
    initial = build_initial_target(source)
    scope = CrawlScope.from_config(source.config)
    output = [initial] if scope.allows(initial.fetch_url, 0) and is_allowed_host(initial.fetch_url, source.allowed_hosts) else []
    discover = source.config.get("discover_sitemaps", True)
    configured = source.config.get("sitemap_urls", [])
    if type(discover) is not bool or not isinstance(configured, list) or len(configured) > 100 or any(not isinstance(v, str) for v in configured):
        raise ValueError("discover_sitemaps must be boolean; sitemap_urls must contain at most 100 URL strings")
    parts = urlsplit(source.base_url)
    candidates = [*configured]
    if discover:
        candidates.append(urlunsplit((parts.scheme, parts.netloc, "/sitemap.xml", "", "")))
    seen = {initial.normalized_url}
    for value in candidates:
        normalized = normalize_url(value)
        if normalized not in seen and is_allowed_host(normalized, source.allowed_hosts):
            seen.add(normalized)
            output.append(CrawlTargetCreate(source_id=source.id, fetch_url=normalized,
                normalized_url=normalized, kind="sitemap", priority=initial.priority - 1))
    return output


async def discover_initial_targets(
    page_size: int = 100,
) -> int:
    """Read enabled sources and enqueue initial website URLs."""

    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")

    total_inserted = 0
    offset = 0

    async with SessionFactory() as session:
        async with session.begin():

            while True:
                # Step 1: Read a page of registered sources
                sources = await get_enabled_sources(
                    session=session,
                    limit=page_size,
                    offset=offset,
                )

                if not sources:
                    break

                # Step 2: Convert supported sources into targets
                for source in sources:
                    if source.kind != "website":
                        continue

                    targets = build_initial_targets(source)
                    scope = CrawlScope.from_config(source.config)
                    total_inserted += await enqueue_targets(session, targets, max_pages=scope.max_pages)

                # Step 4: Move to the next page
                offset += len(sources)

                if len(sources) < page_size:
                    break

    return total_inserted
