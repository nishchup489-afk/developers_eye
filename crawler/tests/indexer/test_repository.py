"""Contract tests for the indexer's persistence adapter (no live DB required)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Text, cast, literal
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.asyncio import AsyncSession

from indexer.repository import (
    LockedDocumentState,
    StoredIndexState,
    delete_search_index,
    get_document_for_update,
    get_search_index,
    upsert_search_index,
)
from indexer.vector import SearchVectors

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def fake_session() -> tuple[AsyncMock, MagicMock]:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    session.execute.return_value = result
    return session, result


def vectors() -> SearchVectors:
    return SearchVectors(
        document_id=10,
        source_id=3,
        source_updated_at=NOW,
        text_vector=cast(literal("python", type_=Text()), TSVECTOR()),
        code_vector=cast(literal("async", type_=Text()), TSVECTOR()),
    )


@pytest.mark.asyncio
async def test_get_search_index_loads_only_freshness_metadata():
    session, result = fake_session()
    result.one_or_none.return_value = MagicMock(
        document_id=10, indexed_hash="v2:" + "a" * 64, indexed_at=NOW
    )

    actual = await get_search_index(session, 10)
    assert actual == StoredIndexState(
        document_id=10, indexed_hash="v2:" + "a" * 64, indexed_at=NOW
    )
    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "indexed_hash" in sql and "indexed_at" in sql
    assert "search_vector" not in sql and "code_vector" not in sql


@pytest.mark.asyncio
async def test_get_search_index_returns_none_if_missing():
    session, result = fake_session()
    result.one_or_none.return_value = None
    assert await get_search_index(session, 10) is None


@pytest.mark.asyncio
async def test_get_document_for_update_locks_document():
    session, result = fake_session()
    result.one_or_none.return_value = MagicMock(
        id=10, source_id=3, is_available=True, updated_at=NOW
    )
    actual = await get_document_for_update(session, 10)
    assert actual == LockedDocumentState(
        document_id=10, source_id=3, is_available=True, updated_at=NOW
    )
    sql = str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF document" in sql
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_document_for_update_returns_none_if_missing():
    session, result = fake_session()
    result.one_or_none.return_value = None
    assert await get_document_for_update(session, 10) is None


@pytest.mark.asyncio
async def test_upsert_uses_bound_parameters_and_updates_both_vectors():
    session, result = fake_session()
    result.scalar_one.return_value = 10
    indexed_hash = "v2:" + "a" * 64
    assert await upsert_search_index(session, vectors(), indexed_hash=indexed_hash) == 10
    statement = session.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "ON CONFLICT (document_id) DO UPDATE SET" in sql
    assert "search_vector = excluded.search_vector" in sql
    assert "code_vector = excluded.code_vector" in sql
    assert "indexed_hash = excluded.indexed_hash" in sql
    assert "indexed_at = now()" in sql
    assert indexed_hash in compiled.params.values()
    assert indexed_hash not in sql
    assert "python" in compiled.params.values() and "async" in compiled.params.values()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_hash", ["", "v0:" + "a" * 64, "v1:xyz", "v1:" + "A" * 64])
async def test_upsert_rejects_invalid_hash(bad_hash):
    session, _ = fake_session()
    with pytest.raises(ValueError, match="indexed_hash"):
        await upsert_search_index(session, vectors(), indexed_hash=bad_hash)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", [0, -1, True, "10"])
async def test_repository_rejects_invalid_document_ids(bad_id):
    session, _ = fake_session()
    with pytest.raises(ValueError, match="document_id"):
        await get_search_index(session, bad_id)
    with pytest.raises(ValueError, match="document_id"):
        await get_document_for_update(session, bad_id)
    with pytest.raises(ValueError, match="document_id"):
        await delete_search_index(session, bad_id)
    session.execute.assert_not_awaited()
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_is_idempotent_and_does_not_commit():
    session, _ = fake_session()
    session.scalar.return_value = 10
    assert await delete_search_index(session, 10) is True
    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "DELETE FROM search_index" in sql
    assert "RETURNING search_index.document_id" in sql
    session.scalar.return_value = None
    assert await delete_search_index(session, 10) is False
    session.commit.assert_not_awaited()
