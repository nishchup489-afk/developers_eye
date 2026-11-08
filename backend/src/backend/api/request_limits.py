"""Per-client rate limits for the public search routes."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from time import monotonic

from fastapi import Request


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
