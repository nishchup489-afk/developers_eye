"""Write crawl attempt history for Developer's Eye.

The Worker owns the AsyncSession transaction and commits it.
This module never creates a session, performs HTTP, or schedules retries.
"""

from __future__ import annotations

from sqlalchemy import func, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.crawl_attempt import CrawlAttempt


VALID_OUTCOMES = frozenset({
    "success", "failed", "blocked", "not_modified",
})


async def start_attempt(
    session: AsyncSession,
    target_id: int,
) -> int:
    """Create an unfinished attempt and return its database-generated ID.

    Commit this insert BEFORE doing network I/O so crashes leave an audit row.
    """
    if type(target_id) is not int or target_id <= 0:
        raise ValueError("target_id must be a positive integer")

    statement = (
        insert(CrawlAttempt)
        .values(crawl_target_id=target_id)
        .returning(CrawlAttempt.id)
    )

    attempt_id = await session.scalar(statement)
    if attempt_id is None:
        raise RuntimeError("Database did not return a crawl attempt ID")
    return attempt_id


async def finish_attempt(
    session: AsyncSession,
    attempt_id: int,
    outcome: str,
    *,
    http_status: int | None = None,
    bytes_received: int | None = None,
    error_message: str | None = None,
) -> bool:
    """Finish an attempt once; return False if missing or already finished.

    The Worker decides outcome/retry policy; this only stores the result.
    """
    if type(attempt_id) is not int or attempt_id <= 0:
        raise ValueError("attempt_id must be a positive integer")
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Invalid crawl outcome: {outcome!r}")
    if http_status is not None and (
        type(http_status) is not int or not 100 <= http_status <= 599
    ):
        raise ValueError("http_status must be between 100 and 599")
    if bytes_received is not None and (
        type(bytes_received) is not int or bytes_received < 0
    ):
        raise ValueError("bytes_received must be a non-negative integer")
    if error_message is not None and not isinstance(error_message, str):
        raise TypeError("error_message must be a string or None")

    statement = (
        update(CrawlAttempt)
        .where(
            CrawlAttempt.id == attempt_id,
            CrawlAttempt.finished_at.is_(None),
        )
        .values(
            finished_at=func.clock_timestamp(),
            outcome=outcome,
            http_status=http_status,
            bytes_received=bytes_received,
            error_message=error_message,
        )
        .returning(CrawlAttempt.id)
    )
    return (await session.scalar(statement)) is not None
