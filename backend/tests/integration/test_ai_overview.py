"""PostgreSQL migration, concurrent workers, persistent quotas and leases.

Set TEST_DATABASE_URL or opt into the local configured database with
OVERVIEW_TEST_USE_LOCAL_DB=1. Only a randomly named disposable schema is changed.
"""
import asyncio
import importlib.util
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.ai_overview.store import Outcome, OverviewStore
from backend.core.config import settings
from backend.models.ai_overview import OverviewBudget, OverviewCache


@pytest_asyncio.fixture
async def factory():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url and os.environ.get("OVERVIEW_TEST_USE_LOCAL_DB") == "1":
        url = settings.database_url
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or OVERVIEW_TEST_USE_LOCAL_DB=1")
    schema = "ai_overview_test_" + uuid4().hex
    admin = create_async_engine(url, connect_args={"timeout": 3})
    engine, created = None, False
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        engine = create_async_engine(url, connect_args={"timeout": 3, "server_settings": {"search_path": f'"{schema}", public'}})
        path = Path(__file__).resolve().parents[2] / "alembic/versions/f6b2d8a4c901_ai_overview_state.py"
        spec = importlib.util.spec_from_file_location("overview_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        def upgrade(connection):
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
        async with engine.begin() as connection:
            await connection.run_sync(upgrade)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        if engine:
            await engine.dispose()
        if created:
            assert re.fullmatch(r"ai_overview_test_[0-9a-f]{32}", schema)
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def test_workers_share_generation_and_restart_persistent_cache(factory):
    workers = [OverviewStore(factory), OverviewStore(factory)]
    claims = await asyncio.gather(*(workers[index % 2].claim("same", f"client-{index}", 3000) for index in range(8)))
    owners = [claim.owner for claim in claims if claim.owner]
    assert len(owners) == 1
    assert all(claim.outcome is None for claim in claims)
    await workers[0].finish("same", owners[0], Outcome(overview={"paragraphs": [], "sources": []}))
    restarted = OverviewStore(factory)
    assert (await restarted.claim("same", "other", 3000)).outcome.status == 200
    denied = await restarted.claim("different", "different-ip", 3000)
    assert denied.outcome.status == 429 and denied.outcome.retry_after > 0
    async with factory() as session:
        budget = await session.get(OverviewBudget, "groq")
        assert len(budget.state["day"]) == 1


async def test_provider_cooldown_is_shared_and_durable(factory):
    first = OverviewStore(factory)
    claim = await first.claim("a", "client", 1)
    await first.finish("a", claim.owner, Outcome(status=429, error="Limited", retry_after=120))
    second = OverviewStore(factory)
    outcome = (await second.claim("b", "other-ip", 1)).outcome
    assert outcome.status == 429 and 119 <= outcome.retry_after <= 120
    assert (await second.claim("a", "client", 1)).outcome.status == 429


async def test_expired_lease_recovers_and_stale_worker_cannot_overwrite(factory):
    first, second = OverviewStore(factory), OverviewStore(factory)
    original = await first.claim("a", "client", 1)
    async with factory() as session, session.begin():
        await session.execute(update(OverviewCache).where(OverviewCache.key == "a").values(lease_until=0))
    replacement = await second.claim("a", "client", 1)
    assert replacement.owner and replacement.owner != original.owner
    await first.finish("a", original.owner, Outcome(error="old", status=502))
    assert (await first.claim("a", "client", 1)).outcome is None
    await second.finish("a", replacement.owner, Outcome())
    assert (await first.claim("a", "client", 1)).outcome.status == 200


async def test_failures_stay_reserved_and_cache_cleanup_is_bounded(factory):
    store = OverviewStore(factory)
    claim = await store.claim("failure", "client", 4000)
    await store.finish("failure", claim.owner, Outcome(status=502, error="Provider unavailable"))
    assert (await store.claim("other", "new-ip", 4000)).outcome.status == 429
    async with factory() as session, session.begin():
        now = (await session.scalar(select(func.clock_timestamp()))).timestamp()
        session.add_all(OverviewCache(key=f"cached-{index}", payload={"overview": None}, expires_at=now + 1800,
                                     lease_until=0) for index in range(505))
    await store.claim("small", "new-ip", 1)
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(OverviewCache)) <= 500


async def test_backend_http_flow_uses_shared_state_and_existing_results(factory, monkeypatch):
    import json
    from contextlib import asynccontextmanager
    from httpx import ASGITransport, AsyncClient
    from pydantic import SecretStr
    from backend.ai_overview import provider, service
    from backend.ai_overview.context import verify_context
    from backend.main import app
    from backend.schema.search import SearchResultOut
    import backend.api.search as search_api

    monkeypatch.setattr(settings, "groq_api_key", SecretStr("fake-backend-test-key"))
    monkeypatch.setattr(settings, "ai_overview", True)
    monkeypatch.setattr(service, "store", OverviewStore(factory))
    searches, generations = [], []
    @asynccontextmanager
    async def search_session():
        yield object()
    async def search(session, query, **kwargs):
        searches.append(query)
        return [SearchResultOut(title="Asyncio docs", source="docs", url="https://docs.python.org/3/library/asyncio.html",
                                snippet="Asyncio supports async/await concurrent I/O.", score=1, type="documentation")]
    async def deadline(session): pass
    def generate(content):
        generations.append(content)
        return 200, {}, json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
            "paragraphs": [{"text": "Asyncio supports concurrent I/O with async/await.", "sources": [1]}]})}}]}).encode()
    monkeypatch.setattr(search_api, "SessionFactory", search_session)
    monkeypatch.setattr(search_api, "apply_query_deadline", deadline)
    monkeypatch.setattr(search_api, "search_documents", search)
    monkeypatch.setattr(provider, "_request", generate)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://backend.test") as client:
        response = await client.get("/search", params={"q": "python async"})
        token = response.json()["overview_token"]
        assert verify_context(token).sources[0].title == "Asyncio docs"
        a, b = await asyncio.gather(*(client.post("/search/overview", json={"token": token}) for _ in range(2)))
        assert a.status_code == b.status_code == 200
        assert a.json() == b.json()
        assert a.json()["overview"]["sources"][0]["url"] == response.json()["results"][0]["url"]
        assert searches == ["python async"] and len(generations) == 1
