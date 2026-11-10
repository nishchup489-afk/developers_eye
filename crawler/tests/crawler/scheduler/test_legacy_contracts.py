"""Collect the rollback-only scheduler contract scripts in the normal CI suite."""
import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.mark.asyncio
@pytest.mark.parametrize("script", ["test_complete_target", "test_fail_target", "test_repository"])
async def test_scheduler_script_contract(script):
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("TEST_DATABASE_URL required for scheduler PostgreSQL contracts")
    url = make_url(raw)
    if url.drivername != "postgresql+asyncpg" or "test" not in (url.database or "").casefold():
        pytest.fail("Scheduler contracts require an asyncpg database named with 'test'")

    spec = importlib.util.spec_from_file_location(
        f"scheduler_contract_{script}", Path(__file__).with_name(f"{script}.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_async_engine(raw)
    try:
        # These older scripts import the application factory. Override it before
        # main opens a session, so collection can never write to the app database.
        module.SessionFactory = async_sessionmaker(engine, expire_on_commit=False)
        await module.main()
    finally:
        await engine.dispose()
