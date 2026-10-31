"""Repository tests for vocabulary selection, removal, and document fetching.

PostgreSQL integration tests use connection-local TEMP tables and require
VOCABULARY_TEST_DATABASE_URL pointing to a disposable PostgreSQL test database.
The real application tables and data are not modified.
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
    fetch_indexed_document,
    fetch_pending_removal_ids,
    fetch_pending_sync_rows,
)


NOW = datetime(2026, 10, 30, 18, 0, tzinfo=timezone.utc)
HASH_A = "v1:" + "a" * 64
HASH_B = "v1:" + "b" * 64


def indexed_hash(char: str, version: int = 1) -> str:
    return f"v{version}:" + char * 64


# ---------------------------------------------------------------------------
# Unit tests: no PostgreSQL required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_repository_returns_rows_from_session():
    response = MagicMock()
    response.all.return_value = [(1, HASH_A), (3, HASH_B)]
    session = MagicMock()
    session.execute = AsyncMock(return_value=response)

    result = await fetch_pending_sync_rows(
        session, limit=2, after_document_id=0
    )

    assert result == [(1, HASH_A), (3, HASH_B)]
    session.execute.assert_awaited_once()
    assert session.execute.await_args.args[0].is_select


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
    assert session.scalars.await_args.args[0].is_select


@pytest.mark.asyncio
async def test_returns_mapping_from_session():
    record = {
        "document_id": 101,
        "indexed_hash": HASH_A,
        "title": "Python",
        "description": "Guide",
        "body": "Async Python",
    }
    response = MagicMock()
    response.mappings.return_value.one_or_none.return_value = record
    session = MagicMock()
    session.execute = AsyncMock(return_value=response)

    result = await fetch_indexed_document(
        session, document_id=101, indexed_hash=HASH_A
    )

    assert result == {
        **record,
        "headings": (),
        "code_blocks": (),
        "tags": (),
    }
    session.execute.assert_awaited_once()
    assert session.execute.await_args.args[0].is_select


@pytest.mark.asyncio
async def test_returns_none_when_no_row():
    response = MagicMock()
    response.mappings.return_value.one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=response)

    result = await fetch_indexed_document(
        session, document_id=101, indexed_hash=HASH_A
    )

    assert result is None
    session.execute.assert_awaited_once()


@pytest.mark.parametrize("invalid_id", [0, -1, True, 1.0, "101", None])
@pytest.mark.asyncio
async def test_rejects_bad_document_id_before_query(invalid_id):
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(ValueError, match="document_id"):
        await fetch_indexed_document(
            session, document_id=invalid_id, indexed_hash=HASH_A
        )

    session.execute.assert_not_awaited()


@pytest.mark.parametrize("invalid_hash", ["", None, 123, True])
@pytest.mark.asyncio
async def test_rejects_bad_revision_before_query(invalid_hash):
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(ValueError, match="indexed_hash"):
        await fetch_indexed_document(
            session, document_id=101, indexed_hash=invalid_hash
        )

    session.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# PostgreSQL fixtures: real queries against isolated TEMP tables
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def postgres_session():
    raw_url = os.getenv("VOCABULARY_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("Set VOCABULARY_TEST_DATABASE_URL for PostgreSQL tests")

    pytest.importorskip("asyncpg")
    url = make_url(raw_url)

    if url.get_backend_name() != "postgresql":
        pytest.fail("VOCABULARY_TEST_DATABASE_URL must use PostgreSQL")
    if "test" not in (url.database or "").lower():
        pytest.fail("Refusing to run outside a database with 'test' in its name")

    engine = create_async_engine(
        url.set(drivername="postgresql+asyncpg"),
        poolclass=NullPool,
    )

    try:
        async with engine.connect() as connection:
            # Temporary tables shadow real tables in this connection only.
            # They remain present until this transaction ends.
            await connection.exec_driver_sql(
                """CREATE TEMP TABLE document (
                    id BIGINT PRIMARY KEY,
                    is_available BOOLEAN NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    body TEXT
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

            async with AsyncSession(
                bind=connection, expire_on_commit=False
            ) as session:
                yield session
    finally:
        await engine.dispose()


async def add_document(
    session: AsyncSession,
    document_id: int,
    *,
    available: bool = True,
    updated: datetime | None = None,
    title: str = "Python Async",
    description: str | None = "Guide",
    body: str | None = "Async programming",
) -> None:
    await session.execute(
        text(
            """INSERT INTO document
                (id, is_available, updated_at, title, description, body)
            VALUES
                (:id, :available, :updated, :title, :description, :body)"""
        ),
        {
            "id": document_id,
            "available": available,
            "updated": NOW if updated is None else updated,
            "title": title,
            "description": description,
            "body": body,
        },
    )


async def add_index(
    session: AsyncSession,
    document_id: int,
    rev: str,
    *,
    indexed_at: datetime | None = None,
) -> None:
    await session.execute(
        text(
            """INSERT INTO search_index
                (document_id, indexed_hash, indexed_at)
            VALUES
                (:id, :hash, :indexed_at)"""
        ),
        {
            "id": document_id,
            "hash": rev,
            "indexed_at": NOW if indexed_at is None else indexed_at,
        },
    )


async def add_state(session: AsyncSession, document_id: int, rev: str) -> None:
    await session.execute(
        text(
            """INSERT INTO vocabulary_document_state
                (document_id, indexed_hash)
            VALUES (:id, :hash)"""
        ),
        {"id": document_id, "hash": rev},
    )


# ---------------------------------------------------------------------------
# PostgreSQL integration: candidate selection and removal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_selects_new_and_changed_revisions_only(postgres_session):
    db = postgres_session

    await add_document(db, 1)
    await add_index(db, 1, indexed_hash("a"))  # New: select

    await add_document(db, 2)
    await add_index(db, 2, indexed_hash("b"))
    await add_state(db, 2, indexed_hash("b"))  # Already synced: skip

    await add_document(db, 3)
    await add_index(db, 3, indexed_hash("c"))
    await add_state(db, 3, indexed_hash("d"))  # Changed: select

    await add_document(db, 4, available=False)
    await add_index(db, 4, indexed_hash("e"))  # Unavailable: skip

    await add_document(db, 5, updated=NOW + timedelta(minutes=1))
    await add_index(db, 5, indexed_hash("f"))  # Stale index: skip

    await add_document(db, 6)
    await add_index(db, 6, "reindex:pending")  # Rebuilding: skip

    await add_document(db, 7)  # Not indexed: skip

    await add_document(db, 8)
    await add_index(db, 8, indexed_hash("8", version=2))  # Valid v2: select

    await add_document(db, 9)
    await add_index(db, 9, "v1:invalid")  # Invalid hash: skip

    await add_index(db, 10, indexed_hash("9"))  # Missing document: skip

    rows = await fetch_pending_sync_rows(db, limit=100, after_document_id=0)
    assert rows == [
        (1, indexed_hash("a")),
        (3, indexed_hash("c")),
        (8, indexed_hash("8", version=2)),
    ]

    first = await fetch_pending_sync_rows(db, limit=2, after_document_id=0)
    assert [document_id for document_id, _ in first] == [1, 3]

    second = await fetch_pending_sync_rows(db, limit=2, after_document_id=3)
    assert [document_id for document_id, _ in second] == [8]

    assert await fetch_pending_sync_rows(db, limit=2, after_document_id=8) == []


@pytest.mark.asyncio
async def test_removal_selects_missing_and_unavailable_documents(postgres_session):
    db = postgres_session

    await add_document(db, 1)
    await add_index(db, 1, indexed_hash("a"))
    await add_state(db, 1, indexed_hash("a"))  # Still valid: skip

    await add_state(db, 2, indexed_hash("b"))  # Missing both: remove

    await add_document(db, 3, available=False)
    await add_index(db, 3, indexed_hash("c"))
    await add_state(db, 3, indexed_hash("c"))  # Unavailable: remove

    await add_document(db, 4)
    await add_state(db, 4, indexed_hash("d"))  # No index: remove

    await add_document(db, 5)
    await add_index(db, 5, "reindex:pending")
    await add_state(db, 5, indexed_hash("e"))  # Still indexed: skip

    await add_index(db, 6, indexed_hash("f"))
    await add_state(db, 6, indexed_hash("f"))  # Missing source: remove

    await add_document(db, 7, available=False)  # Never synced: skip

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


# ---------------------------------------------------------------------------
# PostgreSQL integration: fetching source content for vocabulary builder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pg_fetches_complete_current_document(postgres_session):
    await add_document(postgres_session, 101)
    await add_index(postgres_session, 101, HASH_A)

    row = await fetch_indexed_document(
        postgres_session, document_id=101, indexed_hash=HASH_A
    )

    assert row == {
        "document_id": 101,
        "indexed_hash": HASH_A,
        "title": "Python Async",
        "description": "Guide",
        "body": "Async programming",
        "headings": (),
        "code_blocks": (),
        "tags": (),
    }


@pytest.mark.asyncio
async def test_pg_preserves_nullable_fields(postgres_session):
    await add_document(
        postgres_session, 101, description=None, body=None
    )
    await add_index(postgres_session, 101, HASH_A)

    row = await fetch_indexed_document(
        postgres_session, document_id=101, indexed_hash=HASH_A
    )

    assert row is not None
    assert row["title"] == "Python Async"
    assert row["description"] is None
    assert row["body"] is None
    assert row["headings"] == ()
    assert row["code_blocks"] == ()
    assert row["tags"] == ()


@pytest.mark.parametrize(
    "case",
    [
        "revision_changed",
        "reindex_pending",
        "unavailable",
        "source_newer_than_index",
        "missing_index",
        "invalid_revision",
    ],
)
@pytest.mark.asyncio
async def test_pg_rejects_stale_and_unavailable_sources(postgres_session, case):
    overrides = {
        "revision_changed": {"rev": HASH_B},
        "reindex_pending": {"rev": "reindex:pending"},
        "unavailable": {"available": False},
        "source_newer_than_index": {"updated": NOW + timedelta(seconds=1)},
        "missing_index": {"rev": None},
        "invalid_revision": {"rev": "v1:bad"},
    }
    selected = overrides[case]

    await add_document(
        postgres_session,
        101,
        available=selected.get("available", True),
        updated=selected.get("updated"),
    )
    rev = selected.get("rev", HASH_A)
    if rev is not None:
        await add_index(postgres_session, 101, rev)

    row = await fetch_indexed_document(
        postgres_session, document_id=101, indexed_hash=HASH_A
    )
    assert row is None


@pytest.mark.asyncio
async def test_pg_returns_none_when_source_missing(postgres_session):
    assert await fetch_indexed_document(
        postgres_session, document_id=999, indexed_hash=HASH_A
    ) is None
