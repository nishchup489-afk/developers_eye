"""Let async worker cleanup run on container SIGTERM, as it does on cancellation."""
import asyncio
import signal


async def with_sigterm(work):
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(work)
    stopping = False

    def stop():
        nonlocal stopping
        if not stopping:
            stopping = True
            task.cancel()

    installed = False
    try:
        try:
            loop.add_signal_handler(signal.SIGTERM, stop)
            installed = True
        except (NotImplementedError, RuntimeError):
            pass  # Windows event loops do not support POSIX signal handlers.
        try:
            return await task
        except asyncio.CancelledError:
            if not stopping:
                raise
            return 0
    finally:
        if installed:
            loop.remove_signal_handler(signal.SIGTERM)
