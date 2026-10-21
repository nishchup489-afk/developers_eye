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

from backend.models.crawler_frontier import CrawlTarget
from backend.schema.crawler_frontier import CrawlTargetCreate


BATCH_SIZE = 500


async def enqueue_targets(
    session: AsyncSession,
    targets: list[CrawlTargetCreate],
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
