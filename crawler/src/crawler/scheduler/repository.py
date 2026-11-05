"""PostgreSQL frontier: claim, complete, fail and recover crawl targets.

claim_targets() is one atomic statement. It picks hosts that may be requested
now, longest waiting first, takes one due target from each, leases that target
and holds the host. Two workers can never claim the same host at once, and a
waiting host costs nothing, so slots go to hosts that can actually be fetched.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawler_frontier import CrawlTarget
from crawler.writer.attempts import close_abandoned_attempts

# A claim holds its host for this long unless the request finishes sooner. It
# must outlast one HTTP request, and it is what recovers a crashed worker's host.
HOST_HOLD_SECONDS = 60.0

_DUE = """
    ct.host = {host}
    AND ct.state = 'queued'
    AND ct.next_fetch_at <= now()
    AND (CAST(:source_id AS bigint) IS NULL OR ct.source_id = :source_id)
"""

# Hosts are chosen before any target is locked. Locking inside the sorted query
# would lock one target of every ready host, not just the hosts in the LIMIT.
_CLAIM = f"""
WITH hosts AS (
    SELECT h.host
    FROM crawl_host h
    WHERE h.next_allowed_at <= clock_timestamp()
      AND (h.backoff_until IS NULL OR h.backoff_until <= clock_timestamp())
      AND EXISTS (
          SELECT 1 FROM crawl_target ct
          JOIN source s ON s.id = ct.source_id AND s.is_enabled
          WHERE {_DUE.format(host="h.host")}
      )
    ORDER BY h.next_allowed_at, h.host
    LIMIT :limit
    FOR UPDATE OF h SKIP LOCKED
), picked AS (
    SELECT hosts.host, t.id AS target_id
    FROM hosts
    CROSS JOIN LATERAL (
        SELECT ct.id
        FROM crawl_target ct
        JOIN source s ON s.id = ct.source_id AND s.is_enabled
        WHERE {_DUE.format(host="hosts.host")}
        ORDER BY ct.priority DESC, ct.depth, ct.next_fetch_at, ct.id
        LIMIT 1
        FOR UPDATE OF ct SKIP LOCKED
    ) t
), held AS (
    UPDATE crawl_host h
    SET next_allowed_at = clock_timestamp() + make_interval(secs => :hold)
    FROM picked p
    WHERE h.host = p.host
)
UPDATE crawl_target t
SET state = 'leased', lease_until = clock_timestamp() + make_interval(secs => :lease)
FROM picked p
WHERE t.id = p.target_id
RETURNING t.*
"""


async def claim_targets(
    session: AsyncSession,
    limit: int = 10,
    lease_seconds: int = 300,
    source_id: int | None = None,
    host_hold_seconds: float = HOST_HOLD_SECONDS,
) -> list[CrawlTarget]:
    """Lease at most one due target per available host. The caller commits."""
    if limit < 1 or lease_seconds < 1:
        raise ValueError("Invalid claim limit or lease duration")

    if source_id is not None and source_id < 1:
        raise ValueError("source_id must be positive")

    result = await session.scalars(
        select(CrawlTarget).from_statement(text(_CLAIM)).execution_options(populate_existing=True),
        {"limit": limit, "lease": lease_seconds, "hold": host_hold_seconds, "source_id": source_id},
    )
    return list(result.all())


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


