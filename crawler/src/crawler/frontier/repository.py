"""
Receive a database session and one validated target.
Convert the Pydantic object into a dictionary using model_dump().
Build a PostgreSQL INSERT statement using insert(CrawlTarget).
Use on_conflict_do_nothing() to prevent duplicates.
Use returning(CrawlTarget.id) to determine whether a row was inserted.
Return True if inserted, otherwise False.
"""




from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func, select

from backend.models.crawler_frontier import CrawlTarget
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate
from crawler.frontier.scope import CrawlScope, DEFAULT_MAX_PAGES


BATCH_SIZE = 500


async def enqueue_targets(
    session: AsyncSession,
    targets: list[CrawlTargetCreate],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> int:
    """
    Insert multiple crawl targets into PostgreSQL.

    - Processes targets in batches of 500.
    - Ignores duplicate (source_id, normalized_url) pairs.
    - Returns the number of newly inserted targets.
    - Transaction management belongs to the caller.
        """
    if not targets:
        return 0
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")

    # Deduplicate while preserving the first occurrence.
    unique_targets = {}

    for target in targets:
        key = (target.source_id, target.normalized_url)
        unique_targets.setdefault(key, target)

    # Sort by the same key used by the database uniqueness constraint.
    ordered_targets = [
        unique_targets[key]
        for key in sorted(unique_targets)
    ]

    bounded_targets = []
    for source_id in sorted({target.source_id for target in ordered_targets}):
        # All enqueue callers share this transaction lock, including separate workers.
        await session.execute(select(func.pg_advisory_xact_lock(
            func.hashtextextended(f"frontier-source:{source_id}", 0)
        )))
        config = await session.scalar(select(Source.config).where(Source.id == source_id))
        if config is None:
            raise ValueError(f"Source {source_id} does not exist")
        source_limit = min(max_pages, CrawlScope.from_config(config).max_pages)
        count = await session.scalar(select(func.count(CrawlTarget.id)).where(CrawlTarget.source_id == source_id))
        remaining = max(0, source_limit - count)
        if not remaining:
            continue
        candidates = [target for target in ordered_targets if target.source_id == source_id]
        existing = set((await session.scalars(select(CrawlTarget.normalized_url).where(
            CrawlTarget.source_id == source_id,
            CrawlTarget.normalized_url.in_([target.normalized_url for target in candidates]),
        ))).all())
        bounded_targets.extend([target for target in candidates if target.normalized_url not in existing][:remaining])
    ordered_targets = bounded_targets

    inserted_count = 0

    for start in range(0, len(ordered_targets), BATCH_SIZE):
        batch = ordered_targets[start:start + BATCH_SIZE]

        dataset = [
            target.model_dump()
            for target in batch
        ]

        stmt = (
            insert(CrawlTarget)
            .values(dataset)
            .on_conflict_do_nothing(
                index_elements=[
                    CrawlTarget.source_id,
                    CrawlTarget.normalized_url,
                ]
            )
            .returning(CrawlTarget.id)
        )

        result = await session.execute(stmt)
        inserted_count += len(result.scalars().all())

    return inserted_count


async def enqueue_target(session: AsyncSession, target: CrawlTargetCreate) -> bool:
    """Single-target compatibility entry point; uses the same source budget."""
    return bool(await enqueue_targets(session, [target]))
