"""Continuous worker slots: no batch barrier, no over-claiming, clean shutdown."""
import asyncio
from types import SimpleNamespace

import pytest
import asyncpg
from sqlalchemy.exc import OperationalError, TimeoutError as PoolTimeoutError

from crawler.worker import runner


def target(number):
    return SimpleNamespace(id=number, source_id=1, fetch_url=f"https://example.com/{number}",
                           lease_until=None, host="example.com")


@pytest.fixture
def worker(monkeypatch):
    """A fake frontier; `limits` records the size of each claim."""
    state = SimpleNamespace(queue=[], limits=[], fail_next=0, error=OperationalError("claim", {}, Exception("database down")))

    async def claim_slots(config, limit):
        if state.fail_next:
            state.fail_next -= 1
            raise state.error
        state.limits.append(limit)
        taken, state.queue[:limit] = state.queue[:limit], []
        return taken

    async def no_reaper():
        await asyncio.Event().wait()

    async def no_failure_record(*args):
        return None

    monkeypatch.setattr(runner, "claim_slots", claim_slots)
    monkeypatch.setattr(runner, "reap_forever", no_reaper)
    monkeypatch.setattr(runner, "record_runner_failure", no_failure_record)
    monkeypatch.setattr(runner, "DATABASE_RETRY_SECONDS", 0.01)
    return state


async def run_until(condition, config, handler):
    task = asyncio.create_task(runner.run_continuous(config=config, job_handler=handler))
    try:
        async with asyncio.timeout(3):
            while not condition():
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


CONFIG = runner.RunnerConfig(concurrency=2, batch_size=2, forever=True, poll_seconds=0.01)


async def test_slow_job_does_not_hold_up_a_free_slot(worker):
    worker.queue = [target(1), target(2), target(3), target(4)]
    finished, release_slow = [], asyncio.Event()

    async def handler(job):
        if job.id == 1:
            await release_slow.wait()
        finished.append(job.id)
        return SimpleNamespace(outcome="success")

    await run_until(lambda: {2, 3, 4} <= set(finished), CONFIG, handler)
    assert 1 not in finished


async def test_never_claims_more_than_free_slots(worker):
    worker.queue = [target(number) for number in range(1, 9)]
    active, peak = 0, 0

    async def handler(job):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return SimpleNamespace(outcome="success")

    await run_until(lambda: not worker.queue and active == 0, CONFIG, handler)
    assert peak <= 2
    assert max(worker.limits) <= 2


async def test_claim_database_failure_retries_instead_of_stopping(worker):
    worker.fail_next = 2
    worker.queue = [target(1)]
    finished = []

    async def handler(job):
        finished.append(job.id)
        return SimpleNamespace(outcome="success")

    await run_until(lambda: finished == [1], CONFIG, handler)


@pytest.mark.parametrize("error", [
    PoolTimeoutError("QueuePool limit reached"),
    asyncpg.CannotConnectNowError("the database system is starting up"),
    ConnectionRefusedError("connection refused"),
])
async def test_claim_retries_for_every_way_the_database_can_be_unavailable(worker, error):
    worker.fail_next, worker.error = 2, error
    worker.queue = [target(1)]
    finished = []

    async def handler(job):
        finished.append(job.id)
        return SimpleNamespace(outcome="success")

    await run_until(lambda: finished == [1], CONFIG, handler)


async def test_shutdown_cancels_running_jobs_and_leaves_them_to_lease_expiry(worker):
    worker.queue = [target(1)]
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def handler(job):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    await run_until(started.is_set, CONFIG, handler)
    assert cancelled.is_set()
