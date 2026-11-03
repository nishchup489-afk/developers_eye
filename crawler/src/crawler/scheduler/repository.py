
"""
4. Logic we're going to implement
Step 1 - Filter eligible targets
state == "queued" and next_fetch_at <= NOW()


Step 2 - Prioritize
ORDER BY priority DESC, next_fetch_at ASC, id ASC


Step 3 - Acquire locks
FOR UPDATE SKIP LOCKED and apply LIMIT


Step 4 - Update claimed rows
Set state = "leased" and lease_until = NOW() + lease_seconds


Step 5 - Return claimed targets
Use UPDATE ... RETURNING. Caller commits the transaction before dispatching work.

"""



from datetime import datetime, timedelta

from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawler_frontier import CrawlTarget
from backend.models.crawl_attempt import CrawlAttempt
from crawler.writer.attempts import close_abandoned_attempts


from collections import deque
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.source import Source
from backend.models.crawler_frontier import CrawlTarget


async def claim_targets(
    session: AsyncSession,
    limit: int = 10,
    lease_seconds: int = 300,
    source_id: int | None = None,
) -> list[CrawlTarget]:

    if limit < 1 or lease_seconds < 1:
        raise ValueError("Invalid claim limit or lease duration")

    if source_id is not None and source_id < 1:
        raise ValueError("source_id must be positive")

    eligible = (
        select(CrawlTarget.id)
        .where(
            CrawlTarget.source_id == Source.id,
            CrawlTarget.state == "queued",
            CrawlTarget.next_fetch_at <= func.now(),
        )
        .correlate(Source)
        .exists()
    )

    # Round-robin order: never-claimed sources first, then the one that
    # waited longest. Source rows are NOT locked here, so several workers
    # can claim different targets of the same source at the same time.
    source_query = (  # round robin
        select(Source.id)
        .where(
            Source.is_enabled.is_(True),
            eligible,
        )
        .order_by(
            Source.last_claimed_at.asc().nulls_first(),
            Source.id.asc(),
        )
        .limit(limit)
    )

    if source_id is not None:
        source_query = source_query.where(Source.id == source_id)

    claimed: list[CrawlTarget] = []
    turns: dict[int, datetime] = {}
    seen: set[int] = set()
    queue: deque[int] = deque()
    more_sources = True

    while len(claimed) < limit:

        if not queue:
            if not more_sources:
                break

            page = list(await session.scalars(
                source_query.where(Source.id.not_in(seen)) if seen else source_query
            ))
            seen.update(page)
            queue.extend(page)
            more_sources = len(page) == limit

            if not queue:
                break

        selected_source = queue.popleft()

        target_query = (  # priority scheduling
            select(CrawlTarget)
            .where(
                CrawlTarget.source_id == selected_source,
                CrawlTarget.state == "queued",
                CrawlTarget.next_fetch_at <= func.now(),
            )
            .order_by(
                CrawlTarget.priority.desc(),
                CrawlTarget.depth.asc(),
                CrawlTarget.next_fetch_at.asc(),
                CrawlTarget.id.asc(),
            )
            .limit(1)
            .with_for_update(
                of=CrawlTarget,
                skip_locked=True,
            )
        )

        target = await session.scalar(target_query)

        # Nothing due, or every due target is leased by another worker:
        # drop the source for the rest of this call.
        if target is None:
            continue

        now = await session.scalar(
            select(func.clock_timestamp())
        )

        target.state = "leased"
        target.lease_until = now + timedelta(
            seconds=lease_seconds
        )

        # Flush now: SKIP LOCKED does not skip rows this transaction
        # already locked, so the next query must see this one as leased.
        await session.flush()
        claimed.append(target)

        turns[selected_source] = now
        queue.append(selected_source)

    # Record each source's last turn. Updating in source-id order gives every
    # worker the same lock order, so two claims can wait on each other's
    # source rows but never deadlock. GREATEST keeps the clock moving forward.
    for claimed_source in sorted(turns):
        await session.execute(
            update(Source)
            .where(Source.id == claimed_source)
            .values(
                last_claimed_at=func.greatest(
                    Source.last_claimed_at,
                    turns[claimed_source],
                )
            )
        )

    return claimed



    

async def recover_expired_leases(
    session: AsyncSession,
) -> int:

    rows = (await session.scalars(select(CrawlTarget).where(
        CrawlTarget.state == 'leased',
        or_(CrawlTarget.lease_until <= func.clock_timestamp(), CrawlTarget.lease_until.is_(None)),
    ).order_by(CrawlTarget.id).limit(500).with_for_update(skip_locked=True))).all()
    for row in rows:
        await close_abandoned_attempts(session, row.id, 'lease_expired', 'Worker lease expired; retry scheduled')
        row.failure_count += 1
        row.next_fetch_at = await session.scalar(select(func.clock_timestamp())) + timedelta(
            seconds=calculate_retry_delay(row.failure_count))
        row.state, row.lease_until = 'queued', None

    # Historical attempts have no lease token. A non-leased target proves none is active.
    orphans = (await session.scalars(select(CrawlTarget).where(
        CrawlTarget.state != 'leased',
        select(CrawlAttempt.id).where(CrawlAttempt.crawl_target_id == CrawlTarget.id,
            CrawlAttempt.finished_at.is_(None)).exists(),
    ).order_by(CrawlTarget.id).limit(500).with_for_update(skip_locked=True))).all()
    for row in orphans:
        await close_abandoned_attempts(session, row.id, 'worker', 'Abandoned attempt reconciled; target has no active lease')
    return len(rows)







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
            CrawlTarget.lease_until > func.clock_timestamp(),
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
            CrawlTarget.lease_until > func.clock_timestamp(),
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
            CrawlTarget.lease_until > func.clock_timestamp(),
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


