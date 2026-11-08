"""The indexer worker keeps polling through a database outage."""
import asyncio
from collections import Counter

import asyncpg
import pytest
from sqlalchemy.exc import OperationalError, TimeoutError as PoolTimeoutError

from indexer.config import IndexerConfig
from indexer.worker import runner

ERRORS = [
    OperationalError("select", {}, Exception("database down")),
    PoolTimeoutError("QueuePool limit reached"),
    asyncpg.CannotConnectNowError("the database system is starting up"),
    ConnectionRefusedError("connection refused"),
]


@pytest.fixture
def indexer(monkeypatch):
    monkeypatch.setattr(runner, "DATABASE_RETRY_SECONDS", 0.01)

    async def nothing_to_drain(factory):
        return 0

    monkeypatch.setattr(runner, "drain_vocabulary_changes", nothing_to_drain)
    return IndexerConfig(poll_seconds=0.01)


def report():
    return runner.BatchReport(outcomes=Counter(), end_of_index_scan=True, end_of_removal_scan=True)


@pytest.mark.parametrize("error", ERRORS)
async def test_forever_mode_retries_when_selection_loses_the_database(monkeypatch, indexer, error):
    calls = 0

    async def run_batch(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise error
        return report()

    monkeypatch.setattr(runner, "run_batch", run_batch)
    task = asyncio.create_task(runner.run_worker(None, config=indexer, forever=True))
    try:
        async with asyncio.timeout(3):
            while calls < 3:
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled(), "the worker must still be running when the database returns"


async def test_cursors_are_kept_across_an_outage(monkeypatch, indexer):
    seen, calls = [], 0

    async def run_batch(*args, index_cursor, removal_cursor, **kwargs):
        nonlocal calls
        await asyncio.sleep(0)
        calls += 1
        seen.append(index_cursor)
        if calls == 2:
            raise ConnectionRefusedError("connection refused")
        result = report()
        result.next_index_cursor = 50
        result.end_of_index_scan = False
        return result

    monkeypatch.setattr(runner, "run_batch", run_batch)
    task = asyncio.create_task(runner.run_worker(None, config=indexer, forever=True))
    try:
        async with asyncio.timeout(3):
            while calls < 3:
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert seen[:3] == [0, 50, 50]


async def test_one_shot_mode_reports_the_outage(monkeypatch, indexer):
    async def run_batch(*args, **kwargs):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(runner, "run_batch", run_batch)
    with pytest.raises(ConnectionRefusedError):
        await runner.run_worker(None, config=indexer, forever=False)


@pytest.mark.parametrize("error", ERRORS)
async def test_vocabulary_drain_outage_does_not_stop_indexing(monkeypatch, indexer, error):
    calls = 0

    async def run_batch(*args, **kwargs):
        nonlocal calls
        calls += 1
        return report()

    async def drain(factory):
        raise error

    monkeypatch.setattr(runner, "run_batch", run_batch)
    monkeypatch.setattr(runner, "drain_vocabulary_changes", drain)
    task = asyncio.create_task(runner.run_worker(None, config=indexer, forever=True))
    try:
        async with asyncio.timeout(3):
            while calls < 2:
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
