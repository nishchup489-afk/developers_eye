"""Small committed checkpoints; document bodies and raw HTML never enter events."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
import logging
import os
import socket
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from backend.db.session import SessionFactory
from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawl_monitor import CrawlEvent, CrawlWorker

logger = logging.getLogger(__name__)
worker_id: ContextVar[str | None] = ContextVar("crawler_worker_id", default=None)
active_targets: ContextVar[dict | None] = ContextVar("crawler_active_targets", default=None)


def event(session, attempt_id, stage, outcome, details=None):
    session.add(CrawlEvent(attempt_id=attempt_id, worker_id=worker_id.get(),
                           stage=stage, outcome=outcome, details=details or {}))


async def checkpoint(factory, attempt_id, stage, outcome, details=None, measurements=None):
    # Monitoring outages must not turn a valid fetch into a failed crawl.
    try:
        async with factory() as session, session.begin():
            event(session, attempt_id, stage, outcome, details)
            if measurements is not None:
                await session.execute(update(CrawlAttempt).where(CrawlAttempt.id == attempt_id, CrawlAttempt.finished_at.is_(None))
                                      .values(telemetry=dict(measurements)))
    except Exception:
        logger.exception("Could not persist crawl checkpoint for attempt=%s", attempt_id)


class WorkerMonitor:
    def __init__(self, config):
        self.id = str(uuid4())
        self.config = config
        self.started = datetime.now(timezone.utc)
        self.last_active = self.started
        self.targets = {}
        self.task = None

    async def write(self, stopped=False):
        now = datetime.now(timezone.utc)
        if self.targets:
            self.last_active = now
        values = dict(id=self.id, hostname=socket.gethostname(), pid=os.getpid(),
                      started_at=self.started, heartbeat_at=now, stopped_at=now if stopped else None,
                      last_active_at=self.last_active, concurrency=self.config.concurrency,
                      batch_size=self.config.batch_size, active_targets=list(self.targets.values()))
        try:
            async with SessionFactory() as session, session.begin():
                statement = insert(CrawlWorker).values(**values)
                await session.execute(statement.on_conflict_do_update(index_elements=[CrawlWorker.id], set_=values))
        except Exception:
            logger.exception("Could not persist worker heartbeat")

    async def pulse(self):
        while True:
            await asyncio.sleep(5)
            await self.write()

    async def __aenter__(self):
        self.worker_token = worker_id.set(self.id)
        self.targets_token = active_targets.set(self.targets)
        await self.write()
        self.task = asyncio.create_task(self.pulse())
        return self

    async def __aexit__(self, *args):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        self.targets.clear()
        await self.write(stopped=True)
        active_targets.reset(self.targets_token)
        worker_id.reset(self.worker_token)
