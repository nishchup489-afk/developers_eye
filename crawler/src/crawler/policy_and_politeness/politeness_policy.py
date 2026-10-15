"""Per-host politeness limits for the Developer's Eye async crawler.

In-memory, single-event-loop coordination only. Use a shared limiter when
running multiple crawler processes or machines.

The caller must independently enforce host allowlists, DNS/IP safety,
robots.txt rules, and redirect policy. Keep a slot until the response body
has been consumed or closed.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from crawler.frontier.urls import normalize_url
from crawler.policy_and_politeness.host_policy import normalize_hostname


DEFAULT_MAX_CONCURRENT_PER_HOST = 2
DEFAULT_MIN_INTERVAL_SECONDS = 2.0
DEFAULT_BACKOFF_SECONDS = 60.0
MAX_BACKOFF_SECONDS = 3_600.0


@dataclass(slots=True)
class _HostState:
    semaphore: asyncio.BoundedSemaphore
    timing_lock: asyncio.Lock
    next_allowed_at: float = 0.0
    backoff_until: float = 0.0


def get_host_key(url: str) -> str:
    """Use the normalized hostname as the limit key, across ports/schemes."""
    if not isinstance(url, str):
        raise TypeError("url must be a string")

    parts = urlsplit(normalize_url(url))
    if parts.scheme not in ("http", "https") or parts.hostname is None:
        raise ValueError("Only absolute HTTP(S) URLs are supported")

    host = normalize_hostname(parts.hostname)
    if host is None:
        raise ValueError("Invalid hostname")
    return host


def parse_retry_after(value: str | None) -> float | None:
    """Parse HTTP Retry-After seconds or an HTTP-date; None if invalid."""
    if value is None:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        seconds = float(value)
        return seconds if math.isfinite(seconds) else float(MAX_BACKOFF_SECONDS)
    try:
        date = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())


class PolitenessManager:
    """Limit concurrent connections, request starts, and backoff per host."""

    def __init__(
        self,
        *,
        max_concurrent_per_host: int = DEFAULT_MAX_CONCURRENT_PER_HOST,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        default_backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        max_backoff_seconds: float = MAX_BACKOFF_SECONDS,
    ) -> None:
        if (isinstance(max_concurrent_per_host, bool)
                or not isinstance(max_concurrent_per_host, int)
                or max_concurrent_per_host < 1):
            raise ValueError("max_concurrent_per_host must be a positive integer")

        for name, value, minimum in (
            ("min_interval_seconds", min_interval_seconds, 0.0),
            ("default_backoff_seconds", default_backoff_seconds, 0.0),
            ("max_backoff_seconds", max_backoff_seconds, 0.0),
        ):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < minimum):
                raise ValueError(f"{name} must be a finite non-negative number")
        if max_backoff_seconds <= 0:
            raise ValueError("max_backoff_seconds must be positive")

        self.max_concurrent_per_host = max_concurrent_per_host
        self.min_interval_seconds = float(min_interval_seconds)
        self.default_backoff_seconds = float(default_backoff_seconds)
        self.max_backoff_seconds = float(max_backoff_seconds)
        self._states: dict[str, _HostState] = {}

    def _get_host_state(self, host: str) -> _HostState:
        """Get/create state without an await (atomic within one event loop)."""
        state = self._states.get(host)
        if state is None:
            state = _HostState(
                semaphore=asyncio.BoundedSemaphore(self.max_concurrent_per_host),
                timing_lock=asyncio.Lock(),
            )
            self._states[host] = state
        return state

    async def _wait_for_turn(self, state: _HostState) -> None:
        """Reserve a request start; sleep outside the timing lock."""
        while True:
            async with state.timing_lock:
                now = time.monotonic()
                wait = max(state.next_allowed_at, state.backoff_until) - now
                if wait <= 0:
                    state.next_allowed_at = now + self.min_interval_seconds
                    return
            await asyncio.sleep(wait)

    async def acquire(self, url: str) -> str:
        """Wait for a host slot and a legal request start; return its host key."""
        host = get_host_key(url)
        state = self._get_host_state(host)
        await state.semaphore.acquire()
        try:
            await self._wait_for_turn(state)
        except BaseException:
            state.semaphore.release()
            raise
        return host

    def release(self, host: str) -> None:
        """Release a host key returned by acquire()."""
        state = self._states.get(host)
        if state is None:
            raise ValueError("Unknown host key; acquire() must run first")
        state.semaphore.release()

    async def apply_backoff(self, url: str, seconds: float) -> None:
        """Pause new request starts, without shortening existing backoff."""
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds) or seconds < 0):
            raise ValueError("Backoff seconds must be finite and non-negative")
        state = self._get_host_state(get_host_key(url))
        duration = min(float(seconds), self.max_backoff_seconds)
        async with state.timing_lock:
            state.backoff_until = max(
                state.backoff_until, time.monotonic() + duration
            )

    async def record_response(
        self,
        url: str,
        status_code: int,
        retry_after: str | None = None,
    ) -> None:
        """Back off on 429/503, honoring Retry-After when valid."""
        if status_code not in (429, 503):
            return
        seconds = parse_retry_after(retry_after)
        if seconds is None:
            seconds = self.default_backoff_seconds
        await self.apply_backoff(url, seconds)

    @asynccontextmanager
    async def polite_slot(self, url: str) -> AsyncIterator[None]:
        """Hold a concurrency slot until the response is fully handled."""
        host = await self.acquire(url)
        try:
            yield
        finally:
            self.release(host)
