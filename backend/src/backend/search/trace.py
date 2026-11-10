"""Per-request search stage timings (ADR-0057).

The API sets a fresh dict in `search_trace` before running a search, and the
service adds the milliseconds each stage took. Asyncio tasks copy the context,
but they share this one dict, so a search that times out still shows which
stage it was in. Outside a request nothing is recorded.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

search_trace: ContextVar[dict[str, float] | None] = ContextVar("search_trace", default=None)

STAGES = ("retrieval", "ranking", "metadata", "snippets")


@contextmanager
def stage(name: str) -> Iterator[None]:
    trace = search_trace.get()
    if trace is None:
        yield
        return
    trace["current"] = STAGES.index(name)
    started = perf_counter()
    try:
        yield
    finally:
        trace[name] = round(trace.get(name, 0.0) + (perf_counter() - started) * 1000, 1)


def started_trace() -> dict[str, float]:
    trace: dict[str, float] = {}
    search_trace.set(trace)
    return trace


def stage_summary(trace: dict[str, float]) -> tuple[dict[str, float], str | None]:
    """(milliseconds per finished stage, stage running when the search stopped)."""
    timings = {name: trace[name] for name in STAGES if name in trace}
    current = trace.get("current")
    last = STAGES[int(current)] if current is not None else None
    return timings, last


__all__ = ["STAGES", "search_trace", "stage", "stage_summary", "started_trace"]
