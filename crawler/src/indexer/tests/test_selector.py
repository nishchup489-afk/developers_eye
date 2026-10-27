"""Selector integration tests against REAL PostgreSQL query semantics.

A disposable schema is created and rolled back within a single transaction.
These tests never touch your application's existing tables or data.

Set TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test to run.
Without it, only the selector tests are skipped.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.sqltypes import Enum as SAEnum
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from indexer.selector import (
    is_index_current,
    select_index_candidates,
    select_removal_candidates,
)

BASE_TIME = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


def _q(name: str) -> str:
    """Quote trusted SQLAlchemy metadata identifiers with PostgreSQL's rules."""
    return postgresql.dialect().identifier_preparer.quote(name)


def _test_table_sql(table) -> str:
    """Create a test-only table with the mapped types but WITHOUT production FKs.

    All columns are nullable except primary keys. The fixture inserts only
    fields used by selector.py, leaving unrelated crawler columns empty.
    """
    columns: list[str] = []
    for column in table.columns:
        sql_type = (
            "TEXT" if isinstance(column.type, SAEnum)
            else column.type.compile(dialect=postgresql.dialect())
        )
        constraint = " PRIMARY KEY" if column.primary_key else ""
        columns.append(f"{_q(column.name)} {sql_type}{constraint}")
    return f"CREATE TABLE {_q(table.name)} ({', '.join(columns)})"


@pytest_asyncio.fixture
async def selector_db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL test database")
    if not url.startswith(("postgresql+asyncpg://", "postgresql+psycopg://")):
        pytest.fail("TEST_DATABASE_URL must use an async PostgreSQL driver")

    engine = create_async_engine(url, pool_pre_ping=True)
    schema = "indexer_test_" + uuid4().hex[:16]
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text(f"CREATE SCHEMA {_q(schema)}"))
                await connection.execute(
                    text(f"SET LOCAL search_path TO {_q(schema)}, public")
                )
                await connection.execute(text(_test_table_sql(Document.__table__)))
                await connection.execute(text(_test_table_sql(SearchIndex.__table__)))

                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
            finally:
                # CREATE SCHEMA, tables and rows were all inside this transaction.
                # Rolling it back removes everything automatically.
                await transaction.rollback()
    finally:
        await engine.dispose()


async def add_document(
    session: AsyncSession,
    document_id: int,
    *,
    updated_at: datetime = BASE_TIME,
    is_available: bool = True,
) -> None:
    table = _q(Document.__table__.name)
    await session.execute(
        text(
            f"INSERT INTO {table} (id, updated_at, is_available) "
            "VALUES (:id, :updated_at, :is_available)"
        ),
        {"id": document_id, "updated_at": updated_at, "is_available": is_available},
    )


async def add_index(
    session: AsyncSession,
    document_id: int,
    *,
    indexed_at: datetime,
    indexed_hash: str,
) -> None:
    table = _q(SearchIndex.__table__.name)
    await session.execute(
        text(
            f"INSERT INTO {table} (document_id, indexed_at, indexed_hash) "
            "VALUES (:document_id, :indexed_at, :indexed_hash)"
        ),
        {"document_id": document_id, "indexed_at": indexed_at, "indexed_hash": indexed_hash},
    )


@pytest.mark.asyncio
async def test_new_document_needs_indexing(selector_db, config):
    await add_document(selector_db, 10)
    assert not await is_index_current(selector_db, 10, config=config)

    candidates = await select_index_candidates(selector_db, config=config)
    assert [item.document_id for item in candidates] == [10]
    assert candidates[0].source_updated_at == BASE_TIME


@pytest.mark.asyncio
async def test_current_document_is_skipped(selector_db, config):
    await add_document(selector_db, 10)
    await add_index(
        selector_db, 10,
        indexed_at=BASE_TIME + timedelta(seconds=2),
        indexed_hash=config.index_hash_prefix + "a" * 64,
    )
    assert await is_index_current(selector_db, 10, config=config)
    assert await select_index_candidates(selector_db, config=config) == []


@pytest.mark.asyncio
async def test_changed_document_is_reselected(selector_db, config):
    await add_document(selector_db, 10)
    await add_index(
        selector_db, 10,
        indexed_at=BASE_TIME - timedelta(seconds=1),
        indexed_hash=config.index_hash_prefix + "a" * 64,
    )
    assert not await is_index_current(selector_db, 10, config=config)
    assert [c.document_id for c in await select_index_candidates(selector_db, config=config)] == [10]


@pytest.mark.asyncio
async def test_old_index_version_is_reselected(selector_db, config):
    await add_document(selector_db, 10)
    await add_index(
        selector_db, 10,
        indexed_at=BASE_TIME + timedelta(seconds=1),
        indexed_hash="v0:" + "a" * 64,
    )
    assert not await is_index_current(selector_db, 10, config=config)
    assert [c.document_id for c in await select_index_candidates(selector_db, config=config)] == [10]


@pytest.mark.asyncio
async def test_unavailable_document_is_not_indexed_and_is_removed(selector_db, config):
    await add_document(selector_db, 10, is_available=False)
    await add_index(
        selector_db, 10,
        indexed_at=BASE_TIME,
        indexed_hash=config.index_hash_prefix + "a" * 64,
    )
    candidates = await select_index_candidates(selector_db, config=config)
    assert candidates == []
    assert 10 in await select_removal_candidates(selector_db, config=config)


@pytest.mark.asyncio
async def test_missing_source_document_triggers_cleanup(selector_db, config):
    await add_index(
        selector_db, 99,
        indexed_at=BASE_TIME,
        indexed_hash=config.index_hash_prefix + "a" * 64,
    )
    assert 99 in await select_removal_candidates(selector_db, config=config)


@pytest.mark.asyncio
async def test_cursor_and_batch_size(selector_db, config):
    for document_id in (10, 20, 30):
        await add_document(selector_db, document_id)

    # Already scanned document 10: return the next two candidates.
    candidates = await select_index_candidates(
        selector_db, config=config, after_document_id=10
    )
    assert [c.document_id for c in candidates] == [20, 30]
