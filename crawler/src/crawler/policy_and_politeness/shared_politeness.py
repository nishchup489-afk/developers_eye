"""Per-host politeness shared by every crawler process through PostgreSQL.

One crawl_host row per hostname holds the earliest legal start of the next
request. A request takes the host by pushing that time HOLD_SECONDS ahead, and
finishing sets it to now + the minimum gap. So at most one request runs per host
across all processes, the gap holds, and a crashed worker's hold just expires.

claim_targets() takes the hold in the same statement that leases a target, so
workers never claim work for a busy host. That first request is "prepaid": the
job marks it with prepay() and acquire() skips the database once for that host.
Later requests in the job (the page after robots.txt, redirects) wait normally.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from crawler.policy_and_politeness.politeness_policy import PolitenessManager, get_host_key
from crawler.scheduler.repository import HOST_HOLD_SECONDS

MAX_WAIT_SECONDS = 30.0
POLL_SECONDS = 0.1

_TAKE = text("""
    UPDATE crawl_host SET next_allowed_at = clock_timestamp() + make_interval(secs => :hold)
    WHERE host = :host AND next_allowed_at <= clock_timestamp()
      AND (backoff_until IS NULL OR backoff_until <= clock_timestamp())
    RETURNING host
""")
_WAIT = text("""
    SELECT EXTRACT(EPOCH FROM COALESCE(backoff_until, now()) - clock_timestamp())
    FROM crawl_host WHERE host = :host
""")
_REGISTER = text("INSERT INTO crawl_host (host) VALUES (:host) ON CONFLICT (host) DO NOTHING")
_FINISH = text("""
    UPDATE crawl_host SET next_allowed_at = clock_timestamp() + make_interval(secs => :gap)
    WHERE host = :host
""")
_BACKOFF = text("""
    INSERT INTO crawl_host (host, backoff_until)
    VALUES (:host, clock_timestamp() + make_interval(secs => :seconds))
    ON CONFLICT (host) DO UPDATE SET backoff_until = GREATEST(crawl_host.backoff_until, EXCLUDED.backoff_until)
""")

_prepaid_host: ContextVar[str | None] = ContextVar("crawler_prepaid_host", default=None)
logger = logging.getLogger(__name__)


class HostBusyError(TimeoutError):
    """The host stayed unavailable for too long; the job should retry later."""


class SharedPolitenessManager(PolitenessManager):
    """PolitenessManager with its limits enforced across processes."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        hold_seconds: float = HOST_HOLD_SECONDS,
        max_wait_seconds: float = MAX_WAIT_SECONDS,
        **limits,
    ) -> None:
        super().__init__(**limits)
        self.session_factory = session_factory
        self.hold_seconds = float(hold_seconds)
        self.max_wait_seconds = float(max_wait_seconds)
        self.poll_seconds = POLL_SECONDS

    def prepay(self, host: str) -> None:
        """Record that claim_targets() already took this task's first slot."""
        _prepaid_host.set(host or None)

    async def settle(self) -> None:
        """Free a prepaid hold the job never used, so the host is not idled."""
        host = _prepaid_host.get()
        if host is not None:
            _prepaid_host.set(None)
            await self._finish(host)

    async def _try_take(self, host: str) -> float | None:
        """Take the host. Otherwise return how long its backoff has left.

        Returns None when taken. A remaining hold is not a useful wait estimate,
        because the holder usually finishes long before the hold would expire.
        """
        async with self.session_factory() as session, session.begin():
            take = {"host": host, "hold": self.hold_seconds}
            taken = await session.scalar(_TAKE, take)
            if taken is not None:
                return None
            backoff = await session.scalar(_WAIT, {"host": host})
            if backoff is None:  # First visit, e.g. a redirect to a new host.
                await session.execute(_REGISTER, {"host": host})
                return None if await session.scalar(_TAKE, take) is not None else 0.0
            return max(float(backoff), 0.0)

    async def acquire(self, url: str) -> str:
        host = get_host_key(url)
        if _prepaid_host.get() == host:
            _prepaid_host.set(None)
            return host
        deadline = time.monotonic() + self.max_wait_seconds
        while True:
            backoff = await self._try_take(host)
            if backoff is None:
                return host
            if backoff > self.max_wait_seconds or time.monotonic() >= deadline:
                raise HostBusyError(f"Host {host} stayed unavailable")
            await asyncio.sleep(max(min(backoff, 1.0), self.poll_seconds) + random.uniform(0.0, 0.03))

    async def _finish(self, host: str) -> None:
        try:
            async with self.session_factory() as session, session.begin():
                await session.execute(_FINISH, {"host": host, "gap": self.interval_for(host)})
        except Exception:
            # The hold expires on its own, so this only slows the host briefly.
            logger.warning("Could not release host %s", host, exc_info=True)

    @asynccontextmanager
    async def polite_slot(self, url: str) -> AsyncIterator[None]:
        host = await self.acquire(url)
        try:
            yield
        finally:
            await asyncio.shield(self._finish(host))

    async def apply_backoff(self, url: str, seconds: float) -> None:
        duration = min(float(seconds), self.max_backoff_seconds)
        async with self.session_factory() as session, session.begin():
            await session.execute(_BACKOFF, {"host": get_host_key(url), "seconds": duration})
