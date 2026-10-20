
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



from datetime import datetime

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawler_frontier import CrawlTarget


async def claim_targets(
    session: AsyncSession,
    limit: int = 10,
    lease_seconds: int = 300,
    source_id: int | None = None,
) -> list[CrawlTarget]:

    if limit <= 0:
        raise ValueError("limit must be positive")

    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    if source_id is not None and source_id <= 0:
        raise ValueError("source_id must be positive")

    # Select eligible queued targets
    statement = select(CrawlTarget).where(
        CrawlTarget.state == "queued",
        CrawlTarget.next_fetch_at <= func.now(),
    )

    # Optional source-specific filtering
    if source_id is not None:
        statement = statement.where(
            CrawlTarget.source_id == source_id
        )

    statement = (
        statement
        .order_by(
            CrawlTarget.priority.desc(),
            CrawlTarget.next_fetch_at.asc(),
            CrawlTarget.id.asc(),
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.scalars(statement)
    targets = result.all()

    target_ids = [target.id for target in targets]

    if not target_ids:
        return []

    # Lease the selected targets
    update_statement = (
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

    result = await session.scalars(update_statement)

    return list(result.all())



    

async def recover_expired_leases(
    session: AsyncSession,
) -> int:

    update_stmt = (
        update(CrawlTarget)
        .where(
            CrawlTarget.state == "leased",
            CrawlTarget.lease_until <= func.now(),
        )
        .values(
            state="queued",
            lease_until=None,
        )
        .returning(CrawlTarget.id)
    )

    result = await session.execute(update_stmt)

    recovered_ids = result.scalars().all()

    return len(recovered_ids)







async def complete_target(
    session: AsyncSession,
    target_id: int,
    expected_lease_until: datetime,
    crawl_interval_seconds: int,
) -> bool:
    """
    Complete a successfully crawled target.

    - Verify the target still has its original active lease.
    - Change state from leased to queued.
    - Clear the lease.
    - Record the successful fetch time.
    - Schedule the next crawl.
    - Reset consecutive failures.

    Transaction management belongs to the caller.
    """

    # Step 1: Validate parameters
    if target_id <= 0:
        raise ValueError("target_id must be positive")

    if crawl_interval_seconds <= 0:
        raise ValueError("crawl_interval_seconds must be positive")

    if (
        expected_lease_until.tzinfo is None
        or expected_lease_until.utcoffset() is None
    ):
        raise ValueError("expected_lease_until must be timezone-aware")

    # Step 2: Update only if the original lease is still valid
    update_stmt = (
        update(CrawlTarget)
        .where(
            CrawlTarget.id == target_id,
            CrawlTarget.state == "leased",
            CrawlTarget.lease_until == expected_lease_until,
            CrawlTarget.lease_until > func.now(),
        )
        .values(
            state="queued",
            lease_until=None,
            last_fetched_at=func.now(),
            next_fetch_at=func.now() + func.make_interval(
                0, 0, 0, 0, 0, 0, crawl_interval_seconds
            ),
            failure_count=0,
        )
        .returning(CrawlTarget.id)
    )

    # Step 3: Execute and retrieve the completed target ID
    completed_id = await session.scalar(update_stmt)

    # Step 4: Return whether completion succeeded
    return completed_id is not None






def calculate_retry_delay(
    failure_count: int,
    base_delay_seconds: int = 60,
    max_delay_seconds: int = 3600,
) -> int:
    """Calculate a capped exponential retry delay."""

    if failure_count <= 0:
        raise ValueError("failure_count must be positive")

    if base_delay_seconds <= 0:
        raise ValueError("base_delay_seconds must be positive")

    if max_delay_seconds < base_delay_seconds:
        raise ValueError(
            "max_delay_seconds must be >= base_delay_seconds"
        )

    # Double the delay after each consecutive failure.
    # Cap the exponent to avoid creating enormous integers.
    exponent = min(
        failure_count - 1,
        max_delay_seconds.bit_length(),
    )

    delay = base_delay_seconds * (2 ** exponent)

    return min(delay, max_delay_seconds)


async def fail_target(
    session: AsyncSession,
    target_id: int,
    expected_lease_until: datetime,
    base_delay_seconds: int = 60,
    max_delay_seconds: int = 3600,
) -> bool:
    """
    Mark a leased crawl target as failed.

    - Verify that the original lease is still valid.
    - Increment its consecutive failure count.
    - Calculate exponential retry backoff.
    - Clear the lease.
    - Requeue the target for a future retry.

    The caller owns the database transaction.
    """

    # Step 1: Validate parameters
    if target_id <= 0:
        raise ValueError("target_id must be positive")

    if base_delay_seconds <= 0:
        raise ValueError("base_delay_seconds must be positive")

    if max_delay_seconds < base_delay_seconds:
        raise ValueError(
            "max_delay_seconds must be >= base_delay_seconds"
        )

    if (
        expected_lease_until.tzinfo is None
        or expected_lease_until.utcoffset() is None
    ):
        raise ValueError(
            "expected_lease_until must be timezone-aware"
        )

    # Step 2: Find the target and lock it
    select_stmt = (
        select(CrawlTarget.failure_count)
        .where(
            CrawlTarget.id == target_id,
            CrawlTarget.state == "leased",
            CrawlTarget.lease_until == expected_lease_until,
            CrawlTarget.lease_until > func.now(),
        )
        .with_for_update()
    )

    current_failure_count = await session.scalar(select_stmt)

    # Target missing, lease expired, or ownership changed
    if current_failure_count is None:
        return False

    # Step 3: Calculate the next failure count
    new_failure_count = current_failure_count + 1

    # Step 4: Calculate the retry delay
    retry_delay = calculate_retry_delay(
        failure_count=new_failure_count,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )

    # Step 5: Update the target
    update_stmt = (
        update(CrawlTarget)
        .where(
            CrawlTarget.id == target_id,
            CrawlTarget.state == "leased",
            CrawlTarget.lease_until == expected_lease_until,
            CrawlTarget.lease_until > func.now(),
        )
        .values(
            state="queued",
            lease_until=None,
            failure_count=CrawlTarget.failure_count + 1,
            next_fetch_at=func.now() + func.make_interval(
                0, 0, 0, 0, 0, 0, retry_delay
            ),
        )
        .returning(CrawlTarget.id)
    )

    # Step 6: Execute the update
    failed_id = await session.scalar(update_stmt)

    # Step 7: Return whether the failure was recorded
    return failed_id is not None


