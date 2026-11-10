"""Per-minute search outcomes, recorded in memory and written in the background.

The API runs several processes, so counters in one process would show only the
requests that process happened to serve. Each process keeps its own minutes and
upserts them to search_minute. A search never waits on this write, and minutes
stay in memory while the database is down, which is when they matter most.

Each row belongs to one process, and every write replaces it with the full
count so far, so a retried write cannot count anything twice.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
import os
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from backend.core.config import settings
from backend.db.session import SessionFactory
from backend.models.search_minute import SearchMinute
from backend.models.search_quality import SearchSlowQuery

logger = logging.getLogger(__name__)

# Upper bounds in ms. A successful search slower than the last one lands in the overflow bucket.
LATENCY_BOUNDS_MS = (10, 25, 50, 100, 250, 500, 1000, 2000, 3000, 5000, 10000)
OUTCOMES = ("successful", "invalid", "busy", "timed_out", "database_errors", "engine_errors", "server_errors")
FLUSH_SECONDS = 15.0
FLUSH_TIMEOUT_SECONDS = 10.0
PRUNE_SECONDS = 3600.0
MAX_MINUTES_IN_MEMORY = 120
# ADR-0057: only searches at or over this many ms, or timed out, keep their query text.
SLOW_QUERY_MS = int(os.environ.get("SEARCH_SLOW_QUERY_MS", "1000"))
MAX_SLOW_IN_MEMORY = 200
MAX_SLOW_QUERY_CHARS = 256


def _new_buckets() -> list[int]:
    return [0] * (len(LATENCY_BOUNDS_MS) + 1)


def bucket_index(latency_ms: float) -> int:
    return next((i for i, bound in enumerate(LATENCY_BOUNDS_MS) if latency_ms <= bound), len(LATENCY_BOUNDS_MS))


def _current_minute() -> datetime:
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


@dataclass(slots=True)
class MinuteCounts:
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(OUTCOMES, 0))
    latency_sum_ms: int = 0
    latency_buckets: list[int] = field(default_factory=_new_buckets)
    dirty: bool = True


class SearchTelemetry:
    def __init__(self, process: str | None = None) -> None:
        # The suffix keeps a restarted process with a reused pid from overwriting its old row.
        self.process = process or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:6]}"
        self._minutes: dict[datetime, MinuteCounts] = {}
        self._failing = False
        self._next_prune = 0.0
        self._slow: deque[dict] = deque(maxlen=MAX_SLOW_IN_MEMORY)

    def record_slow(
        self, *, query: str, mode: str, category: str | None, page: int, outcome: str,
        elapsed_ms: float, result_count: int | None, stages: dict[str, float], stopped_in: str | None,
    ) -> bool:
        """Keep one slow or timed-out search for the admin slow-query list."""
        if outcome != "timed_out" and elapsed_ms < SLOW_QUERY_MS:
            return False
        self._slow.append(dict(
            recorded_at=datetime.now(timezone.utc), process=self.process,
            query=query[:MAX_SLOW_QUERY_CHARS], mode=mode, category=category, page=page, outcome=outcome,
            elapsed_ms=round(elapsed_ms), result_count=result_count, stages=dict(stages), stopped_in=stopped_in,
        ))
        return True

    def slow_rows(self) -> list[dict]:
        """Slow searches not yet written, newest last."""
        return list(self._slow)

    def record(self, outcome: str, latency_ms: float | None = None) -> None:
        now = _current_minute()
        minute = self._minutes.get(now)
        if minute is None:
            minute = self._minutes[now] = MinuteCounts()
            for old in sorted(self._minutes)[:-MAX_MINUTES_IN_MEMORY]:
                del self._minutes[old]
        minute.counts[outcome] += 1
        minute.dirty = True
        if outcome == "successful" and latency_ms is not None:
            minute.latency_sum_ms += round(latency_ms)
            minute.latency_buckets[bucket_index(latency_ms)] += 1

    def _row(self, at: datetime, minute: MinuteCounts) -> dict:
        return dict(minute=at, process=self.process, **minute.counts, latency_sum_ms=minute.latency_sum_ms,
                    latency_buckets=list(minute.latency_buckets))

    def rows(self) -> list[dict]:
        """Everything still in memory, in the shape of search_minute rows."""
        return [self._row(at, minute) for at, minute in sorted(self._minutes.items())]

    async def flush(self, factory=SessionFactory) -> None:
        dirty = {at: minute for at, minute in self._minutes.items() if minute.dirty}
        prune = monotonic() >= self._next_prune
        slow = list(self._slow)
        if not dirty and not prune and not slow:
            return
        rows = [self._row(at, minute) for at, minute in dirty.items()]
        for minute in dirty.values():
            minute.dirty = False
        try:
            async with factory() as session, session.begin():
                if rows:
                    statement = insert(SearchMinute).values(rows)
                    columns = (*OUTCOMES, "latency_sum_ms", "latency_buckets")
                    await session.execute(statement.on_conflict_do_update(
                        index_elements=["minute", "process"],
                        set_={name: statement.excluded[name] for name in columns}))
                if slow:
                    await session.execute(insert(SearchSlowQuery).values(slow))
                if prune:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.admin_event_retention_days)
                    await session.execute(delete(SearchMinute).where(SearchMinute.minute < cutoff))
                    await session.execute(delete(SearchSlowQuery).where(SearchSlowQuery.recorded_at < cutoff))
        except BaseException:
            for minute in dirty.values():
                minute.dirty = True
            raise
        for row in slow:
            # Rows recorded during the write stay queued for the next flush.
            if self._slow and self._slow[0] is row:
                self._slow.popleft()
        if prune:
            self._next_prune = monotonic() + PRUNE_SECONDS
        # The current minute stays: later searches add to the same row.
        current = _current_minute()
        for at in dirty:
            minute = self._minutes.get(at)
            if minute is not None and not minute.dirty and at < current:
                del self._minutes[at]

    async def flush_quietly(self) -> None:
        try:
            async with asyncio.timeout(FLUSH_TIMEOUT_SECONDS):
                await self.flush()
            self._failing = False
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            # A pending migration fails every write, so say it once per outage.
            if not self._failing:
                logger.warning("Search telemetry write failed (%s); retrying", type(exc).__name__)
            self._failing = True

    async def run(self, interval: float = FLUSH_SECONDS) -> None:
        while True:
            await asyncio.sleep(interval)
            await self.flush_quietly()


telemetry = SearchTelemetry()
