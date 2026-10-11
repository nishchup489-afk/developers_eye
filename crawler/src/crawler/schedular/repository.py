
"""
4. Logic we're going to implement
Step 1 — Filter eligible targets
state == "queued" and next_fetch_at <= NOW()


Step 2 — Prioritize
ORDER BY priority DESC, next_fetch_at ASC, id ASC


Step 3 — Acquire locks
FOR UPDATE SKIP LOCKED and apply LIMIT


Step 4 — Update claimed rows
Set state = "leased" and lease_until = NOW() + lease_seconds


Step 5 — Return claimed targets
Use UPDATE ... RETURNING. Caller commits the transaction before dispatching work.

"""



from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawler_frontier import CrawlTarget


async def claim_targets(
    session: AsyncSession,
    limit: int = 10,
    lease_seconds: int = 300,
) -> list[CrawlTarget]:

    # Step 1: Validate parameters
    if limit <= 0:
        raise ValueError("limit must be positive")

    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    # Step 2: Select eligible targets and lock them
    target_stmt = (
        select(CrawlTarget)
        .where(
            CrawlTarget.state == "queued",
            CrawlTarget.next_fetch_at <= func.now(),
        )
        .order_by(
            CrawlTarget.priority.desc(),
            CrawlTarget.next_fetch_at.asc(),
            CrawlTarget.id.asc(),
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(target_stmt)

    selected_targets = result.scalars().all()

    # Step 3: Extract selected IDs
    target_ids = [
        target.id for target in selected_targets
    ]

    if not target_ids:
        return []

    # Step 4: Update selected targets to leased
    update_stmt = (
        update(CrawlTarget)
        .where(CrawlTarget.id.in_(target_ids))
        .values(
            state="leased",
            lease_until=func.now() + func.make_interval(
                0, 0, 0, 0, 0, 0, lease_seconds
            ),
        )
        .returning(CrawlTarget)
        .execution_options(populate_existing=True)
    )

    # Step 5: Execute and retrieve updated targets
    result = await session.execute(update_stmt)

    claimed_targets = result.scalars().all()

    return list(claimed_targets)


    
    # 1. Validate limit and lease_seconds


    # 2. SELECT eligible CrawlTarget rows

    # 3. ORDER BY priority DESC

    # 4. LIMIT number of selected rows

    # 5. FOR UPDATE SKIP LOCKED

    # 6. Retrieve selected target IDs

    # 7. UPDATE selected rows:
    #    state = "leased"
    #    lease_until = NOW() + lease duration

    # 8. RETURN updated targets