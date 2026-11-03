"""Tests for search.retrieval.code.

Unit tests need no database. The optional PostgreSQL integration test runs only
when TEST_DATABASE_URL is set to an async PostgreSQL URL. Use a dedicated TEST
DATABASE: a temporary table shadows the real search_index for the transaction.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.search.retrieval.code import (
    MAX_OFFSET,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    CodeRetrievalHit,
    search_code,
)


def fake_session(rows: list[dict] | None = None) -> AsyncMock:
    session = AsyncMock()
    result = Mock()
    mappings = Mock()
    mappings.all.return_value = rows or []
    result.mappings.return_value = mappings
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_returns_typed_sorted_hits_from_database():
    session = fake_session(
        [
            {"document_id": 42, "score": 0.8},
            {"document_id": 7, "score": 0.6},
        ]
    )

    hits = await search_code(session, "APIRouter")

    assert hits == [CodeRetrievalHit(42, 0.8), CodeRetrievalHit(7, 0.6)]
    assert all(isinstance(hit, CodeRetrievalHit) for hit in hits)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_normalizes_query_and_binds_pagination():
    session = fake_session()

    assert await search_code(session, "\t FastAPI\n  APIRouter  ", limit=12, offset=8) == []
    sql, params = session.execute.await_args.args
    assert params == {"query_text": "FastAPI APIRouter", "limit": 12, "offset": 8}
    assert "FROM search_index" in str(sql)
    assert "code_vector @@" in str(sql)
    assert "plainto_tsquery('simple'" in str(sql)
    assert "ts_rank_cd(" in str(sql)
    assert "ORDER BY score DESC, si.document_id ASC" in str(sql)


@pytest.mark.asyncio
async def test_defaults_are_correct():
    session = fake_session()
    await search_code(session, "include_router")
    assert session.execute.await_args.args[1] == {
        "query_text": "include_router",
        "limit": 50,
        "offset": 0,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", " ", " \n \t ", "\u2003"])
async def test_blank_query_never_hits_database(query: str):
    session = fake_session()
    assert await search_code(session, query) == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [None, 17, ["hello"], {"query": "hello"}])
async def test_invalid_query_type_is_rejected(query):
    session = fake_session()
    with pytest.raises(TypeError, match="query must be a string"):
        await search_code(session, query)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_at_max_length_is_accepted():
    session = fake_session()
    await search_code(session, "x" * MAX_QUERY_CHARS)
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_over_max_length_is_rejected():
    session = fake_session()
    with pytest.raises(ValueError, match="at most"):
        await search_code(session, "x" * (MAX_QUERY_CHARS + 1))
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["abc\x00def", "abc\x01def", "abc\x7fdef"])
async def test_control_characters_are_rejected(query: str):
    session = fake_session()
    with pytest.raises(ValueError, match="control characters"):
        await search_code(session, query)
    session.execute.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1, MAX_RESULTS + 1, 1.5, "10", None, True, False])
async def test_invalid_limit_rejected(limit):
    session = fake_session()
    with pytest.raises(ValueError, match="limit"):
        await search_code(session, "python", limit=limit)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [-1, MAX_OFFSET + 1, 2.5, "0", None, True, False])
async def test_invalid_offset_rejected(offset):
    session = fake_session()
    with pytest.raises(ValueError, match="offset"):
        await search_code(session, "python", offset=offset)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_pagination_upper_boundaries_are_accepted():
    session = fake_session()
    await search_code(session, "python", limit=MAX_RESULTS, offset=MAX_OFFSET)
    assert session.execute.await_args.args[1]["limit"] == MAX_RESULTS
    assert session.execute.await_args.args[1]["offset"] == MAX_OFFSET


@pytest.mark.asyncio
async def test_user_input_is_parameterized_not_interpolated_into_sql():
    session = fake_session()
    suspicious = "x'); DROP TABLE search_index; --"
    await search_code(session, suspicious)
    sql, params = session.execute.await_args.args
    assert suspicious not in str(sql)
    assert params["query_text"] == suspicious
    assert ":query_text" in str(sql)


@pytest.mark.asyncio
async def test_unicode_query_is_passed_to_postgres():
    session = fake_session()
    await search_code(session, "解析 asyncio")
    assert session.execute.await_args.args[1]["query_text"] == "解析 asyncio"


@pytest.mark.asyncio
async def test_empty_result_is_empty_list():
    assert await search_code(fake_session([]), "notfound") == []


@pytest.mark.asyncio
async def test_database_exceptions_are_not_silenced():
    session = fake_session()
    session.execute.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await search_code(session, "FastAPI")


@pytest.mark.asyncio
async def test_identical_document_ids_remain_unmodified():
    session = fake_session([{"document_id": 4, "score": 0.2}])
    hits = await search_code(session, "python")
    assert hits[0].document_id == 4
    assert hits[0].score == 0.2


@pytest.mark.asyncio
async def test_postgresql_temp_index_end_to_end():
    """Real DB check, skipped unless TEST_DATABASE_URL is configured.

    The test uses a temporary table and does not write to the actual index.
    """
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to enable PostgreSQL integration")
    pytest.importorskip("asyncpg")
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must begin with postgresql+asyncpg://")

    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    text(
                        "CREATE TEMP TABLE search_index ("
                        "document_id BIGINT PRIMARY KEY, "
                        "code_vector TSVECTOR NOT NULL) ON COMMIT DROP"
                    )
                )
                await session.execute(
                    text(
                        "CREATE INDEX test_code_vector_gin "
                        "ON search_index USING GIN (code_vector)"
                    )
                )
                await session.execute(
                    text(
                        "INSERT INTO search_index (document_id, code_vector) VALUES "
                        "(1, to_tsvector('simple', 'FastAPI APIRouter include_router')), "
                        "(2, to_tsvector('simple', 'Django views urlpatterns')), "
                        "(3, to_tsvector('simple', 'FastAPI dependency injection'))"
                    )
                )

                hits = await search_code(session, "FastAPI APIRouter")
                assert [hit.document_id for hit in hits] == [1]
                assert hits[0].score > 0
                assert await search_code(session, "not_in_index") == []
                assert await search_code(session, "FastAPI APIRouter", offset=1) == []
    finally:
        await engine.dispose()
