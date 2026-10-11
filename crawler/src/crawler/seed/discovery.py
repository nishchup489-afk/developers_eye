
from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate

from crawler.frontier.urls import normalize_url
from crawler.frontier.repository import enqueue_targets

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
                targets = []

                for source in sources:
                    if source.kind != "website":
                        continue

                    target = build_initial_target(source)
                    targets.append(target)

                # Step 3: Persist the targets
                inserted = await enqueue_targets(
                    session=session,
                    targets=targets,
                )

                total_inserted += inserted

                # Step 4: Move to the next page
                offset += len(sources)

                if len(sources) < page_size:
                    break

    return total_inserted
