"""Deadlines and cancellation of the search routes against real PostgreSQL.

Requires TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test. No rows are
read or written: the search service is replaced by a pg_sleep, so these tests check the
real statement_timeout error, and that an abandoned query really stops on the server.
"""

from __future__ import annotations

import asyncio
import os
from time import perf_counter
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.api.search as search_api
from backend.api.request_limits import RateLimiter
from backend.main import app

MARKER = f"deadline_test_{uuid4().hex}"


async def sleep_in_postgres(session) -> None:
    await session.execute(text(f"SELECT pg_sleep(30) /* {MARKER} */"))


async def sleeping_search(session, query, **kwargs):
    await sleep_in_postgres(session)
    return []


async def sleeping_suggestion(query, session):
    await sleep_in_postgres(session)


@pytest_asyncio.fixture
async def engine(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or "test" not in url.rsplit("/", 1)[-1]:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL database whose name contains 'test'")
    engine = create_async_engine(url)
    monkeypatch.setattr(search_api, "SessionFactory", async_sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(search_api, "search_documents", sleeping_search)
    monkeypatch.setattr(search_api, "suggest_query_correction", sleeping_suggestion)
    monkeypatch.setattr(search_api, "search_rate_limiter", RateLimiter(0, 1))
    monkeypatch.setattr(search_api, "suggest_rate_limiter", RateLimiter(0, 1))
    monkeypatch.setattr(search_api, "_in_flight", asyncio.Semaphore(2))
    try:
        yield engine
    finally:
        await engine.dispose()


async def get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, params={"q": "python"})


async def assert_query_stopped(engine) -> None:
    """The sleeping statement leaves pg_stat_activity well before its 30 seconds are up."""
    for _ in range(40):
        async with engine.connect() as connection:
            running = await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active' "
                    "AND pid <> pg_backend_pid() AND query LIKE :marker"
                ),
                {"marker": f"%{MARKER}%"},
            )
        if running == 0:
            return
        await asyncio.sleep(0.05)
    pytest.fail("the abandoned query is still running in PostgreSQL")


@pytest.mark.parametrize("path", ["/search", "/search/suggest"])
async def test_real_statement_timeout_is_504(engine, monkeypatch, path):
    monkeypatch.setattr(search_api, "QUERY_DEADLINE_MS", 100)
    monkeypatch.setattr(search_api, "TOTAL_DEADLINE_SECONDS", 10)
    started = perf_counter()
    response = await get(path)
    assert response.status_code == 504
    assert perf_counter() - started < 5
    assert "statement timeout" not in response.text
    assert search_api._in_flight._value == 2


@pytest.mark.parametrize("path", ["/search", "/search/suggest"])
async def test_total_deadline_stops_the_postgres_query(engine, monkeypatch, path):
    monkeypatch.setattr(search_api, "QUERY_DEADLINE_MS", 30_000)
    monkeypatch.setattr(search_api, "TOTAL_DEADLINE_SECONDS", 0.3)
    assert (await get(path)).status_code == 504
    assert search_api._in_flight._value == 2
    await assert_query_stopped(engine)


async def test_client_disconnect_stops_the_postgres_query(engine, monkeypatch):
    monkeypatch.setattr(search_api, "QUERY_DEADLINE_MS", 30_000)
    monkeypatch.setattr(search_api, "TOTAL_DEADLINE_SECONDS", 10)
    pending = [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        if pending:
            return pending.pop()
        await asyncio.sleep(0.3)
        return {"type": "http.disconnect"}

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": "/search", "raw_path": b"/search", "root_path": "",
        "query_string": b"q=python", "headers": [(b"host", b"testserver")],
        "client": ("203.0.113.9", 50000), "server": ("testserver", 80),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    assert sent[0]["status"] == 499
    assert search_api._in_flight._value == 2
    await assert_query_stopped(engine)
