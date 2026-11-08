"""Per-client rate limits and client-disconnect handling for the public search routes."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import TypeVar

from fastapi import Request

T = TypeVar("T")

# nginx's convention for "the client closed the connection before the response".
CLIENT_CLOSED_REQUEST = 499


class RateLimiter:
    """Token bucket per client, kept in this process's memory.

    Each uvicorn worker keeps its own buckets, so with N workers one client can
    reach up to N times the configured rate. per_minute <= 0 disables the limit.
    """

    def __init__(
        self,
        per_minute: int,
        burst: int,
        *,
        max_clients: int = 10_000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.rate = per_minute / 60.0
        self.burst = float(max(burst, 1))
        self.max_clients = max_clients
        self._clock = clock
        # client -> (tokens, last update), least recently seen first.
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def acquire(self, client: str) -> float:
        """Spend one token. Returns 0 when allowed, else seconds until the next token."""
        if self.rate <= 0:
            return 0.0
        now = self._clock()
        tokens, updated = self._buckets.pop(client, (self.burst, now))
        tokens = min(self.burst, tokens + (now - updated) * self.rate)
        wait = 0.0
        if tokens >= 1:
            tokens -= 1
        else:
            wait = (1 - tokens) / self.rate
        self._buckets[client] = (tokens, now)
        if len(self._buckets) > self.max_clients:
            # Forgetting a client only refills its bucket, so memory stays bounded.
            self._buckets.popitem(last=False)
        return wait


def client_key(request: Request) -> str:
    """The caller's address. Behind the Next.js proxy, uvicorn's proxy-header handling
    (FORWARDED_ALLOW_IPS) has already replaced it with the browser's address."""
    return request.client.host if request.client else "unknown"


class ClientDisconnected(Exception):
    """The client went away before the response was ready."""


async def _wait_for_disconnect(request: Request) -> None:
    # GET bodies are empty, so the only message left to arrive is http.disconnect.
    while (await request.receive())["type"] != "http.disconnect":
        pass


async def run_unless_disconnected(request: Request, work: Awaitable[T]) -> T:
    """Await work, cancelling it if the client disconnects first.

    The work always finishes unwinding (closing its session and releasing the
    concurrency slot) before this returns or raises, including when the caller
    itself is cancelled by a deadline.
    """
    task = asyncio.ensure_future(work)
    watcher = asyncio.create_task(_wait_for_disconnect(request))
    try:
        await asyncio.wait((task, watcher), return_when=asyncio.FIRST_COMPLETED)
    finally:
        watcher.cancel()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)
    if task.cancelled():
        raise ClientDisconnected
    return task.result()
