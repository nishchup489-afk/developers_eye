"""Repository tests: SQL construction and optional real PostgreSQL behavior.

PostgreSQL tests use TEMP tables, so real application tables are untouched.
Set VOCABULARY_TEST_DATABASE_URL to a disposable database containing 'test'
in its database name, e.g. postgresql+asyncpg://.../developers_eye_test.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from retrieval_vocabulary.repository import (
    fetch_pending_removal_ids,
    fetch_pending_sync_rows,
)


NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


def indexed_hash(char: str, version: int = 1) -> str:
    return f"v{version}:" + char * 64


@pytest.mark.asyncio
async def test_sync_repository_returns_rows_from_session():
    response = MagicMock()
    response.all.return_value = [(1, indexed_hash("a")), (3, indexed_hash("b"))]
    session = MagicMock()
    session.execute = AsyncMock(return_value=response)

    result = await fetch_pending_sync_rows(
        session, limit=2, after_document_id=0
    )

    assert result == [(1, indexed_hash("a")), (3, indexed_hash("b"))]
    session.execute.assert_awaited_once()
    stmt = session.execute.await_args.args[0]
    assert stmt.is_select


@pytest.mark.asyncio
async def test_removal_repository_returns_ids_from_session():
    response = MagicMock()
    response.all.return_value = [5, 8]
    session = MagicMock()
    session.scalars = AsyncMock(return_value=response)

    result = await fetch_pending_removal_ids(
        session, limit=2, after_document_id=4
    )

    assert result == [5, 8]
    session.scalars.assert_awaited_once()
    stmt = session.scalars.await_args.args[0]
    assert stmt.is_select


@pytest_asyncio.fixture
async def postgres_session():
    """Temporary tables within a disposable PostgreSQL test database.

    Missing configuration skips these optional integration tests.
    The same connection is used for TEMP table creation and ORM queries.
    """
    raw_url = os.getenv("VOCABULARY_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Set VOCABULARY_TEST_DATABASE_URL for PostgreSQL tests")

    pytest.importorskip("asyncpg")
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.fail("VOCABULARY_TEST_DATABASE_URL must use PostgreSQL")
    if "test" not in (url.database or "").lower():
        pytest.fail("Refusing to run outside a database with 'test' in its name")

    url = url.set(drivername="postgresql+asyncpg")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            # TEMP tables shadow identically named persistent tables in this
            # connection, without modifying application schema or records.
            await connection.exec_driver_sql(
                """CREATE TEMP TABLE document (
                    id BIGINT PRIMARY KEY,
                    is_available BOOLEAN NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                ) ON COMMIT DROP"""
            )
            await connection.exec_driver_sql(
                """CREATE TEMP TABLE search_index (
                    document_id BIGINT PRIMARY KEY,
                    indexed_hash TEXT NOT NULL,
                    indexed_at TIMESTAMPTZ NOT NULL
                ) ON COMMIT DROP"""
            )
            await connection.exec_driver_sql(
                """CREATE TEMP TABLE vocabulary_document_state (
                    document_id BIGINT PRIMARY KEY,
                    indexed_hash TEXT NOT NULL
                ) ON COMMIT DROP"""
            )
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                yield session
            # Closing the connection rolls the transaction back, removing
            # temporary tables even if an assertion fails.
    finally:
        await engine.dispose()


async def add_document(session, document_id: int, *, available=True, updated=None):
    await session.execute(
        text(
            "INSERT INTO document (id, is_available, updated_at) "
            "VALUES (:id, :available, :updated)"
        ),
        {
            "id": document_id,
            "available": available,
            "updated": NOW if updated is None else updated,
        },
    )


async def add_index(session, document_id: int, rev: str, *, indexed_at=None):
    await session.execute(
        text(
            "INSERT INTO search_index (document_id, indexed_hash, indexed_at) "
            "VALUES (:id, :hash, :indexed_at)"
        ),
        {
            "id": document_id,
            "hash": rev,
            "indexed_at": NOW if indexed_at is None else indexed_at,
        },
    )


async def add_state(session, document_id: int, rev: str):
    await session.execute(
        text(
            "INSERT INTO vocabulary_document_state (document_id, indexed_hash) "
            "VALUES (:id, :hash)"
        ),
        {"id": document_id, "hash": rev},
    )


@pytest.mark.asyncio
async def test_sync_selects_new_and_changed_revisions_only(postgres_session):
    db = postgres_session

    # 1: newly indexed, no vocabulary state -> select
    await add_document(db, 1)
    await add_index(db, 1, indexed_hash("a"))

    # 2: already processed this exact version -> skip
    await add_document(db, 2)
    await add_index(db, 2, indexed_hash("b"))
    await add_state(db, 2, indexed_hash("b"))

    # 3: indexed revision changed -> select
    await add_document(db, 3)
    await add_index(db, 3, indexed_hash("c"))
    await add_state(db, 3, indexed_hash("d"))

    # 4: source unavailable -> skip
    await add_document(db, 4, available=False)
    await add_index(db, 4, indexed_hash("e"))

    # 5: index older than source document -> skip
    await add_document(db, 5, updated=NOW + timedelta(minutes=1))
    await add_index(db, 5, indexed_hash("f"))

    # 6: indexer is rebuilding this document -> skip
    await add_document(db, 6)
    await add_index(db, 6, "reindex:pending")

    # 7: crawled but not indexed -> skip
    await add_document(db, 7)

    # 8: another completed index version -> select
    await add_document(db, 8)
    await add_index(db, 8, indexed_hash("8", version=2))

    # 9: malformed index hash -> skip
    await add_document(db, 9)
    await add_index(db, 9, "v1:invalid")

    # 10: index exists but document missing -> skip
    await add_index(db, 10, indexed_hash("9"))

    rows = await fetch_pending_sync_rows(db, limit=100, after_document_id=0)
    assert rows == [
        (1, indexed_hash("a")),
        (3, indexed_hash("c")),
        (8, indexed_hash("8", version=2)),
    ]

    first = await fetch_pending_sync_rows(db, limit=2, after_document_id=0)
    assert [id_ for id_, _ in first] == [1, 3]
    second = await fetch_pending_sync_rows(db, limit=2, after_document_id=3)
    assert [id_ for id_, _ in second] == [8]
    assert await fetch_pending_sync_rows(db, limit=2, after_document_id=8) == []


@pytest.mark.asyncio
async def test_removal_selects_missing_and_unavailable_documents(postgres_session):
    db = postgres_session

    # 1: still indexed and available -> skip
    await add_document(db, 1)
    await add_index(db, 1, indexed_hash("a"))
    await add_state(db, 1, indexed_hash("a"))

    # 2: document and index missing -> remove vocabulary
    await add_state(db, 2, indexed_hash("b"))

    # 3: source unavailable -> remove vocabulary
    await add_document(db, 3, available=False)
    await add_index(db, 3, indexed_hash("c"))
    await add_state(db, 3, indexed_hash("c"))

    # 4: source available, index missing -> remove vocabulary
    await add_document(db, 4)
    await add_state(db, 4, indexed_hash("d"))

    # 5: index rebuilding, still exists -> do not remove
    await add_document(db, 5)
    await add_index(db, 5, "reindex:pending")
    await add_state(db, 5, indexed_hash("e"))

    # 6: index exists but document missing -> remove vocabulary
    await add_index(db, 6, indexed_hash("f"))
    await add_state(db, 6, indexed_hash("f"))

    # 7: unavailable but never processed -> not selected
    await add_document(db, 7, available=False)

    assert await fetch_pending_removal_ids(
        db, limit=100, after_document_id=0
    ) == [2, 3, 4, 6]
    assert await fetch_pending_removal_ids(
        db, limit=2, after_document_id=0
    ) == [2, 3]
    assert await fetch_pending_removal_ids(
        db, limit=2, after_document_id=3
    ) == [4, 6]
    assert await fetch_pending_removal_ids(
        db, limit=100, after_document_id=6
    ) == []
