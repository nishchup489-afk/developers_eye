from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backend.admin_services.crawler_sessions import merge_spans, worker_span

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def worker(id, start, stop=None, heartbeat=None):
    started = NOW - timedelta(minutes=start)
    return SimpleNamespace(id=id, hostname="h", pid=1, concurrency=4, started_at=started,
                           stopped_at=None if stop is None else NOW - timedelta(minutes=stop),
                           heartbeat_at=NOW - timedelta(minutes=heartbeat if heartbeat is not None else (stop or 0)))


def test_overlapping_workers_form_one_session():
    sessions = merge_spans([worker("a", 60, 30), worker("b", 50, 10), worker("c", 5, 1)], NOW)
    assert [len(s["workers"]) for s in sessions] == [1, 2]  # newest first
    assert sessions[1]["start"] == NOW - timedelta(minutes=60)
    assert sessions[1]["end"] == NOW - timedelta(minutes=10)
    assert not any(s["running"] for s in sessions)


def test_running_worker_extends_session_to_now():
    sessions = merge_spans([worker("a", 30, 20), worker("b", 25, heartbeat=0)], NOW)
    assert len(sessions) == 1 and sessions[0]["running"] and sessions[0]["end"] == NOW


def test_crashed_worker_ends_at_last_heartbeat():
    start, end, running = worker_span(worker("a", 30, heartbeat=15), NOW)
    assert not running and end == NOW - timedelta(minutes=15)
