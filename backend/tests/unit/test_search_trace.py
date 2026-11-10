"""Search stage tracing and the slow-search threshold (ADR-0057)."""

import asyncio

from backend.search import telemetry as telemetry_module
from backend.search.telemetry import SearchTelemetry
from backend.search.trace import search_trace, stage, stage_summary, started_trace


def test_stage_is_a_no_op_outside_a_request():
    search_trace.set(None)
    with stage("retrieval"):
        pass
    assert search_trace.get() is None


def test_trace_records_finished_stages_and_where_a_search_stopped():
    async def search(trace):
        with stage("retrieval"):
            await asyncio.sleep(0)
        with stage("ranking"):
            await asyncio.sleep(10)  # cancelled, like a timed-out search

    async def main():
        trace = started_trace()
        task = asyncio.create_task(search(trace))
        await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return trace

    trace = asyncio.run(main())
    timings, stopped = stage_summary(trace)
    assert set(timings) == {"retrieval", "ranking"}
    assert stopped == "ranking"


def test_only_slow_or_timed_out_searches_keep_query_text(monkeypatch):
    monkeypatch.setattr(telemetry_module, "SLOW_QUERY_MS", 1000)
    t = SearchTelemetry(process="p")
    common = dict(mode="all", category=None, page=1, result_count=None, stages={}, stopped_in=None)
    assert not t.record_slow(query="fast", outcome="successful", elapsed_ms=999, **common)
    assert t.record_slow(query="slow", outcome="successful", elapsed_ms=1000, **common)
    assert t.record_slow(query="cut", outcome="timed_out", elapsed_ms=10, **common)
    assert t.record_slow(query="x" * 400, outcome="timed_out", elapsed_ms=10, **common)
    rows = t.slow_rows()
    assert [r["query"][:4] for r in rows] == ["slow", "cut", "xxxx"]
    assert len(rows[-1]["query"]) == 256
    for i in range(300):
        t.record_slow(query=f"q{i}", outcome="timed_out", elapsed_ms=1, **common)
    assert len(t.slow_rows()) == 200
