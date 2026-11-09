"""Search outcome recording: buckets, percentiles, retries and the offline report."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import backend.api.search as search_api
from backend.admin_services import search_reporting as reporting
from backend.main import app
from backend.search import telemetry as telemetry_module
from backend.search.telemetry import LATENCY_BOUNDS_MS, MAX_MINUTES_IN_MEMORY, SearchTelemetry, bucket_index


def test_bucket_boundaries():
    assert bucket_index(0) == 0
    assert bucket_index(10) == 0
    assert bucket_index(10.1) == 1
    assert bucket_index(10000) == len(LATENCY_BOUNDS_MS) - 1
    assert bucket_index(10001) == len(LATENCY_BOUNDS_MS)


def test_percentile_interpolates_and_handles_edges():
    buckets = [0] * (len(LATENCY_BOUNDS_MS) + 1)
    assert reporting._percentile(buckets, 0.5) is None
    buckets[3] = 100  # 50 to 100 ms
    assert reporting._percentile(buckets, 0.5) == 75
    buckets = [0] * (len(LATENCY_BOUNDS_MS) + 1)
    buckets[-1] = 1
    assert reporting._percentile(buckets, 0.99) == LATENCY_BOUNDS_MS[-1]


def test_memory_is_bounded(monkeypatch):
    telemetry = SearchTelemetry(process="p")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for minute in range(MAX_MINUTES_IN_MEMORY + 10):
        monkeypatch.setattr(telemetry_module, "_current_minute", lambda m=minute: start + timedelta(minutes=m))
        telemetry.record("busy")
    rows = telemetry.rows()
    assert len(rows) == MAX_MINUTES_IN_MEMORY
    assert rows[-1]["minute"] == start + timedelta(minutes=MAX_MINUTES_IN_MEMORY + 9)


class FailingSession:
    async def __aenter__(self):
        raise OperationalError("SELECT 1", {}, Exception("down"))

    async def __aexit__(self, *_):
        return False


@pytest.mark.asyncio
async def test_failed_flush_keeps_minutes_for_the_retry():
    telemetry = SearchTelemetry(process="p")
    telemetry.record("timed_out")
    with pytest.raises(OperationalError):
        await telemetry.flush(FailingSession)
    assert telemetry.rows()[0]["timed_out"] == 1
    assert all(minute.dirty for minute in telemetry._minutes.values())


def test_offline_report_uses_memory_and_says_it_is_partial(monkeypatch):
    memory = SearchTelemetry(process="p")
    for _ in range(9):
        memory.record("database_errors")
    memory.record("successful", 40)
    monkeypatch.setattr(reporting, "telemetry", memory)
    monkeypatch.setattr(reporting, "_expected_revision", lambda: None)
    report = reporting.build_offline_report(hours=1)

    assert report["status"] == "down" and report["partial"] is True and report["recording"] is False
    assert report["database"]["reachable"] is False
    assert report["totals"]["database_errors"] == 9
    assert report["totals"]["availability_percent"] == 10


def test_expected_revision_finds_the_newest_migration(monkeypatch):
    # CI installs the package into site-packages, where alembic.ini does not ship.
    backend = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(reporting, "ALEMBIC_INI", backend / "alembic.ini")
    reporting._expected_revision.cache_clear()
    revision = reporting._expected_revision()
    reporting._expected_revision.cache_clear()
    assert revision and list((backend / "alembic" / "versions").glob(f"{revision}_*.py"))


class Canceled(Exception):
    sqlstate = "57014"


@pytest.fixture
def recorded(monkeypatch):
    memory = SearchTelemetry(process="p")
    monkeypatch.setattr(search_api, "telemetry", memory)

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def no_deadline(session):
        return None

    monkeypatch.setattr(search_api, "apply_query_deadline", no_deadline)
    monkeypatch.setattr(search_api, "SessionFactory", fake_session)
    return memory


@pytest.mark.parametrize("error, outcome, status", [
    (OperationalError("q", {}, Canceled()), "timed_out", 504),
    (OperationalError("q", {}, Exception("gone")), "database_errors", 503),
    (RuntimeError("no snapshot"), "engine_errors", 503),
    (KeyError("bug"), "server_errors", 500),
])
def test_route_records_each_failure(recorded, monkeypatch, error, outcome, status):
    async def failing(*args, **kwargs):
        raise error

    monkeypatch.setattr(search_api, "search_documents", failing)
    response = TestClient(app, raise_server_exceptions=False).get("/search", params={"q": "python"})
    assert response.status_code == status
    assert recorded.rows()[0][outcome] == 1


def test_route_records_success_with_latency(recorded, monkeypatch):
    async def found(*args, **kwargs):
        return []

    monkeypatch.setattr(search_api, "search_documents", found)
    assert TestClient(app).get("/search", params={"q": "python"}).status_code == 200
    assert recorded.rows()[0]["successful"] == 1
    assert sum(recorded.rows()[0]["latency_buckets"]) == 1
