"""Indexer process heartbeat for the admin dashboard (mirrors crawler WorkerMonitor).

A heartbeat failure is logged and ignored: monitoring must never stop indexing.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert

from backend.models.crawl_monitor import IndexerWorker

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 5


class IndexerMonitor:
    def __init__(self, session_factory, *, batch_size: int, concurrency: int):
        self.id = str(uuid4())
        self.factory = session_factory
        self.batch_size = batch_size
        self.concurrency = concurrency
        self.started = datetime.now(timezone.utc)
        self.last_batch: datetime | None = None
        self.indexed = 0
        self.failed = 0
        self.task: asyncio.Task | None = None

    def record(self, *, indexed: int, failed: int) -> None:
        self.last_batch = datetime.now(timezone.utc)
        self.indexed += indexed
        self.failed += failed

    async def write(self, stopped: bool = False) -> None:
        now = datetime.now(timezone.utc)
        values = dict(id=self.id, hostname=socket.gethostname(), pid=os.getpid(), started_at=self.started,
                      heartbeat_at=now, stopped_at=now if stopped else None, last_batch_at=self.last_batch,
                      concurrency=self.concurrency, batch_size=self.batch_size,
                      indexed_total=self.indexed, failed_total=self.failed)
        try:
            async with self.factory() as session, session.begin():
                statement = insert(IndexerWorker).values(**values)
                await session.execute(statement.on_conflict_do_update(index_elements=[IndexerWorker.id], set_=values))
        except Exception:
            logger.exception("Could not persist indexer heartbeat")

    async def _pulse(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await self.write()

    async def __aenter__(self) -> "IndexerMonitor":
        await self.write()
        self.task = asyncio.create_task(self._pulse())
        return self

    async def __aexit__(self, *args) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        await self.write(stopped=True)
