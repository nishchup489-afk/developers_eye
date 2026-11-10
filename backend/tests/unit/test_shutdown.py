import asyncio
import signal

import pytest

from backend.core.shutdown import with_sigterm


@pytest.mark.asyncio
async def test_sigterm_cancels_work_once_and_waits_for_cleanup(monkeypatch):
    loop = asyncio.get_running_loop()
    handlers = {}
    monkeypatch.setattr(loop, "add_signal_handler", lambda sig, callback: handlers.__setitem__(sig, callback))
    monkeypatch.setattr(loop, "remove_signal_handler", lambda sig: handlers.pop(sig))
    started = asyncio.Event()
    cleaned = []

    async def work():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.append(True)

    task = asyncio.create_task(with_sigterm(work()))
    await started.wait()
    handlers[signal.SIGTERM]()
    handlers[signal.SIGTERM]()  # Repeated signals must not interrupt cleanup.
    assert await task == 0
    assert cleaned == [True] and not handlers


@pytest.mark.asyncio
async def test_unsignalled_cancellation_and_errors_are_not_suppressed(monkeypatch):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda *args: None)
    monkeypatch.setattr(loop, "remove_signal_handler", lambda *args: None)

    async def cancelled():
        raise asyncio.CancelledError

    async def failed():
        raise RuntimeError("worker failed")

    with pytest.raises(asyncio.CancelledError):
        await with_sigterm(cancelled())
    with pytest.raises(RuntimeError, match="worker failed"):
        await with_sigterm(failed())
