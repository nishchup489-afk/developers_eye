"""Overload, rate-limit, deadline and cancellation behaviour of /search and /search/suggest.

The database is never touched: sessions and services are stubbed, and slow
queries are simulated with sleeps that record whether they were cancelled.
"""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import backend.api.search as search_api
from backend.api.request_limits import RateLimiter, run_unless_disconnected, ClientDisconnected
from backend.main import app
from backend.schema.search_term import QueryCorrection
from backend.search.config import SearchConfig

client = TestClient(app)


@asynccontextmanager
async def fake_session():
    yield object()


class Probe:
    """Stands in for the search and suggestion services and records what happened."""

    def __init__(self) -> None:
        self.calls = 0
        self.cancelled = False
        self.delay = 0.0
        self.error: Exception | None = None

    async def _run(self):
        self.calls += 1
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.error:
            raise self.error

    async def search(self, session, query, **kwargs):
        await self._run()
        return []

    async def suggest(self, query, session):
        await self._run()
        return QueryCorrection(original_query=query, suggested_query=query, corrections=[])


@pytest.fixture
def probe(monkeypatch):
    probe = Probe()

    async def no_deadline(session):
        return None

    monkeypatch.setattr(search_api, "apply_query_deadline", no_deadline)
    monkeypatch.setattr(search_api, "SessionFactory", fake_session)
    monkeypatch.setattr(search_api, "search_documents", probe.search)
    monkeypatch.setattr(search_api, "suggest_query_correction", probe.suggest)
    monkeypatch.setattr(search_api, "_in_flight", asyncio.Semaphore(2))
    return probe


@pytest.fixture
def outcomes(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(search_api.telemetry, "record", lambda outcome, latency_ms=None: seen.append(outcome))
    return seen


def statement_timeout() -> DBAPIError:
    class QueryCanceled(Exception):
        sqlstate = "57014"

    return DBAPIError("SELECT", {}, QueryCanceled("canceling statement due to statement timeout"))


# ---------------------------------------------------------------- query length


def test_frontend_query_limits_match_the_backend():
    """lib/search.ts cannot import SearchConfig, so a change on one side must fail here."""
    frontend = Path(__file__).parents[3] / "frontend" / "lib" / "search.ts"
    if not frontend.exists():
        pytest.skip("frontend is not part of this checkout")
    source = frontend.read_text(encoding="utf-8")
    config = SearchConfig()
    assert int(re.search(r"maxQueryLength = (\d+);", source)[1]) == config.max_query_length
    assert int(re.search(r"maxRawQueryLength = (\d+);", source)[1]) == config.max_raw_query_length


# ---------------------------------------------------------------- rate limiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_bucket_allows_burst_then_reports_wait_and_refills():
    clock = Clock()
    limiter = RateLimiter(per_minute=60, burst=2, clock=clock)
    assert limiter.acquire("a") == 0
    assert limiter.acquire("a") == 0
    assert limiter.acquire("a") == pytest.approx(1.0)
    clock.now += 0.5
    assert limiter.acquire("a") == pytest.approx(0.5)
    clock.now += 0.5
    assert limiter.acquire("a") == 0


def test_buckets_are_per_client_and_bounded():
    clock = Clock()
    limiter = RateLimiter(per_minute=60, burst=1, max_clients=2, clock=clock)
    assert limiter.acquire("a") == 0
    assert limiter.acquire("b") == 0
    assert limiter.acquire("a") > 0, "a's bucket is empty"
    assert limiter.acquire("c") == 0
    assert len(limiter._buckets) == 2, "the least recently seen client was forgotten"


def test_zero_rate_disables_the_limit():
    limiter = RateLimiter(per_minute=0, burst=1)
    assert all(limiter.acquire("a") == 0 for _ in range(1000))


def test_search_rate_limit_is_429_with_retry_after(monkeypatch, probe):
    monkeypatch.setattr(search_api, "search_rate_limiter", RateLimiter(60, 2))
    assert [client.get("/search", params={"q": "python"}).status_code for _ in range(2)] == [200, 200]
    limited = client.get("/search", params={"q": "python"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"
    assert limited.headers["cache-control"] == "no-store"
    assert probe.calls == 2, "a limited request never reaches the database"


def test_suggest_rate_limit_is_separate_from_search(monkeypatch, probe):
    monkeypatch.setattr(search_api, "search_rate_limiter", RateLimiter(60, 1))
    monkeypatch.setattr(search_api, "suggest_rate_limiter", RateLimiter(60, 1))
    assert client.get("/search", params={"q": "python"}).status_code == 200
    assert client.get("/search/suggest", params={"q": "python"}).status_code == 200
    assert client.get("/search/suggest", params={"q": "python"}).status_code == 429


def test_forwarded_clients_get_their_own_buckets(monkeypatch, probe):
    """Behind Next.js, uvicorn's proxy headers make each browser its own client."""
    monkeypatch.setattr(search_api, "search_rate_limiter", RateLimiter(60, 1))
    proxied = TestClient(ProxyHeadersMiddleware(app, trusted_hosts="*"))

    def get(address):
        return proxied.get("/search", params={"q": "python"}, headers={"X-Forwarded-For": address}).status_code

    assert get("203.0.113.1") == 200
    assert get("203.0.113.2") == 200
    assert get("203.0.113.1") == 429


# ---------------------------------------------------------------- overload


def test_full_concurrency_cap_is_503_with_retry_after(monkeypatch, probe, outcomes):
    monkeypatch.setattr(search_api, "_in_flight", asyncio.Semaphore(0))
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert probe.calls == 0
    assert outcomes == ["busy"]


async def test_concurrent_burst_admits_only_the_cap(probe, outcomes):
    """Requests arriving in the same event-loop turn cannot overshoot the cap."""
    probe.delay = 0.1
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as burst:
        responses = await asyncio.gather(
            *(burst.get("/search", params={"q": "python"}) for _ in range(6))
        )
    assert sorted(r.status_code for r in responses) == [200, 200, 503, 503, 503, 503]
    assert probe.calls == 2
    assert search_api._in_flight._value == 2, "every slot is released"
    assert outcomes.count("busy") == 4


def test_suggestions_share_the_concurrency_cap(monkeypatch, probe):
    monkeypatch.setattr(search_api, "_in_flight", asyncio.Semaphore(0))
    response = client.get("/search/suggest", params={"q": "pyhton"})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert probe.calls == 0


def test_failed_requests_release_their_slot(probe):
    probe.error = OperationalError("SELECT", {}, Exception("connection refused"))
    for path in ("/search", "/search/suggest"):
        assert client.get(path, params={"q": "python"}).status_code == 503
    assert search_api._in_flight._value == 2


def test_validation_failure_does_not_take_a_slot(probe):
    assert client.get("/search", params={"q": "x" * 300}).status_code == 422
    assert search_api._in_flight._value == 2
    assert probe.calls == 0


# ---------------------------------------------------------------- deadlines


def test_total_deadline_is_504_and_cancels_the_search(monkeypatch, probe, outcomes):
    monkeypatch.setattr(search_api, "TOTAL_DEADLINE_SECONDS", 0.05)
    probe.delay = 5
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 504
    assert response.json() == {"detail": "Search timed out"}
    assert probe.cancelled
    assert not search_api._in_flight.locked() and search_api._in_flight._value == 2, "slot released"
    assert outcomes == ["timed_out"]


def test_statement_timeout_is_504(probe, outcomes):
    probe.error = statement_timeout()
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 504
    assert "statement timeout" not in response.text
    assert outcomes == ["timed_out"]


def test_connection_pool_timeout_is_504(probe, outcomes):
    probe.error = PoolTimeoutError("QueuePool limit reached")
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 504
    assert "QueuePool" not in response.text
    assert outcomes == ["timed_out"]


def test_other_database_errors_stay_503(probe, outcomes):
    probe.error = OperationalError("SELECT", {}, Exception("connection refused"))
    assert client.get("/search", params={"q": "python"}).status_code == 503
    assert outcomes == ["database_errors"]


def test_suggest_deadline_and_statement_timeout_are_504(monkeypatch, probe):
    monkeypatch.setattr(search_api, "TOTAL_DEADLINE_SECONDS", 0.05)
    probe.delay = 5
    assert client.get("/search/suggest", params={"q": "pyhton"}).status_code == 504
    assert probe.cancelled
    probe.delay, probe.error = 0, statement_timeout()
    assert client.get("/search/suggest", params={"q": "pyhton"}).status_code == 504


# ---------------------------------------------------------------- client disconnects


async def call_then_disconnect(path: str, query: bytes, after: float = 0.05) -> list[dict]:
    """Drive the ASGI app directly, disconnecting `after` seconds into the request."""
    pending = [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        if pending:
            return pending.pop()
        await asyncio.sleep(after)
        return {"type": "http.disconnect"}

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
        "query_string": query, "headers": [(b"host", b"testserver")],
        "client": ("203.0.113.9", 50000), "server": ("testserver", 80),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=2)
    return sent


async def test_disconnect_cancels_search_and_frees_its_slot(probe, outcomes):
    probe.delay = 5
    sent = await call_then_disconnect("/search", b"q=python")
    assert probe.cancelled
    assert sent[0]["status"] == 499
    assert search_api._in_flight._value == 2
    assert outcomes == [], "a disconnect is neither a success nor a failure"


async def test_disconnect_cancels_suggestion(probe):
    probe.delay = 5
    sent = await call_then_disconnect("/search/suggest", b"q=pyhton")
    assert probe.cancelled
    assert sent[0]["status"] == 499


async def test_finished_work_wins_over_a_later_disconnect():
    class Connected:
        async def receive(self):
            await asyncio.sleep(10)
            return {"type": "http.disconnect"}

    async def quick():
        return 42

    assert await run_unless_disconnected(Connected(), quick()) == 42


async def test_deadline_waits_for_cancelled_work_to_unwind():
    """A deadline that fires mid-search still lets the search close its session first."""
    unwound = asyncio.Event()

    class Connected:
        async def receive(self):
            await asyncio.sleep(10)
            return {"type": "http.disconnect"}

    async def slow():
        try:
            await asyncio.sleep(10)
        finally:
            await asyncio.sleep(0.01)  # e.g. returning a connection to the pool
            unwound.set()

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.02):
            await run_unless_disconnected(Connected(), slow())
    assert unwound.is_set()


async def test_disconnect_raises_client_disconnected():
    class Gone:
        async def receive(self):
            return {"type": "http.disconnect"}

    async def slow():
        await asyncio.sleep(10)

    with pytest.raises(ClientDisconnected):
        await run_unless_disconnected(Gone(), slow())
