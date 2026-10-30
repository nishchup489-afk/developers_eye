"""PostgreSQL integration tests for Developer's Eye full-text retrieval.

These tests shadow the production search_index table with a temporary table.
They do not insert, modify, or remove any production search documents.

Requires:
    pytest, pytest-asyncio, SQLAlchemy, asyncpg
    TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test

Run from the repository's backend directory (with backend/src on PYTHONPATH):
    poetry run pytest src/backend/tests/integration/test_fts.py -v
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.models import SearchIndex
from backend.search.retrieval.fts import get_full_text_search


@pytest_asyncio.fixture
async def fts_session():
    """Isolated PostgreSQL dataset on a single transaction-bound connection."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database to run FTS integration tests")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must use the postgresql+asyncpg driver")
    if SearchIndex.__table__.schema is not None:
        pytest.fail(
            "SearchIndex declares an explicit schema; pg_temp cannot shadow its table. "
            "Use an isolated test schema with that model configuration instead."
        )

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                # pg_temp comes first, so unqualified model queries use this table.
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(
                    text(
                        """
                        CREATE TEMP TABLE search_index (
                            document_id BIGINT PRIMARY KEY,
                            search_vector TSVECTOR NOT NULL,
                            code_vector TSVECTOR NOT NULL
                        ) ON COMMIT DROP
                        """
                    )
                )
                await connection.execute(
                    text("CREATE INDEX test_fts_text_gin ON search_index USING GIN (search_vector)")
                )
                await connection.execute(
                    text("CREATE INDEX test_fts_code_gin ON search_index USING GIN (code_vector)")
                )

                documents = [
                    (11, "python async tutorial", ""),
                    (12, "python async tutorial", ""),
                    (13, "python web guide", "async"),
                    (14, "rust ownership guide", "FastAPI dependency injection"),
                    (15, "python async patterns", "FastAPI async"),
                    (16, "go concurrency guide", "running"),
                    (17, "Running tasks in python", ""),
                    (18, "go pointers", ""),
                ]
                for document_id, body, code in documents:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO search_index (document_id, search_vector, code_vector)
                            VALUES (
                                :document_id,
                                to_tsvector('english', :body),
                                to_tsvector('simple', :code)
                            )
                            """
                        ),
                        {"document_id": document_id, "body": body, "code": code},
                    )

                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
                # Exiting the transaction rolls back all fixture changes.
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_text_matches_and_returns_ranked_fields(fts_session: AsyncSession):
    results = await get_full_text_search("python async", fts_session)

    assert {row["document_id"] for row in results} == {11, 12, 15}
    assert all(row["search_rank"] > 0 for row in results)
    assert all(row["code_rank"] == 0 for row in results)
    assert all(isinstance(row["document_id"], int) for row in results)
    assert all(isinstance(row["search_rank"], float) for row in results)


@pytest.mark.asyncio
async def test_code_only_match_uses_code_vector(fts_session: AsyncSession):
    results = await get_full_text_search("fastapi dependency", fts_session)

    assert [row["document_id"] for row in results] == [14]
    assert results[0]["search_rank"] == 0
    assert results[0]["code_rank"] > 0


@pytest.mark.asyncio
async def test_match_from_either_vector(fts_session: AsyncSession):
    results = await get_full_text_search("async", fts_session)
    by_id = {row["document_id"]: row for row in results}

    assert {11, 12, 13, 15}.issubset(by_id)
    assert by_id[13]["search_rank"] == 0
    assert by_id[13]["code_rank"] > 0
    assert by_id[11]["search_rank"] > 0


@pytest.mark.asyncio
async def test_terms_split_between_vectors_do_not_match(fts_session: AsyncSession):
    # Current semantics: all positive terms must match within at least one vector.
    results = await get_full_text_search("python async", fts_session)

    assert 13 not in {row["document_id"] for row in results}


@pytest.mark.asyncio
async def test_english_stemming_differs_from_simple(fts_session: AsyncSession):
    results = await get_full_text_search("run", fts_session)
    by_id = {row["document_id"]: row for row in results}

    assert 17 in by_id  # English 'Running' stems to 'run'.
    assert by_id[17]["search_rank"] > 0
    assert 16 not in by_id  # Code 'running' is not stemmed by 'simple'.


@pytest.mark.asyncio
async def test_web_style_or_operator(fts_session: AsyncSession):
    results = await get_full_text_search("python OR rust", fts_session)

    assert {row["document_id"] for row in results} == {11, 12, 13, 14, 15, 17}


@pytest.mark.asyncio
async def test_quoted_phrase(fts_session: AsyncSession):
    results = await get_full_text_search('"python async"', fts_session)

    assert {row["document_id"] for row in results} == {11, 12, 15}
    assert 13 not in {row["document_id"] for row in results}


@pytest.mark.asyncio
async def test_no_matches_returns_empty_list(fts_session: AsyncSession):
    assert await get_full_text_search("nonexistentuniquephrase", fts_session) == []


@pytest.mark.asyncio
async def test_case_insensitive_search(fts_session: AsyncSession):
    lower = await get_full_text_search("python async", fts_session)
    upper = await get_full_text_search("PYTHON ASYNC", fts_session)

    assert [r["document_id"] for r in lower] == [r["document_id"] for r in upper]


@pytest.mark.asyncio
async def test_limit_and_deterministic_tie_break(fts_session: AsyncSession):
    results = await get_full_text_search("python async", fts_session, limit=2)

    # All three text matches have identical term positions and should tie.
    assert [row["document_id"] for row in results] == [11, 12]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", " ", "\t  \n"])
async def test_blank_query_does_not_touch_database(query: str):
    session = AsyncMock(spec=AsyncSession)

    assert await get_full_text_search(query, session) == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [None, 42, [], {}])
async def test_non_string_query_rejected_before_database_access(query: object):
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(TypeError, match="query must be a string"):
        await get_full_text_search(query, session)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1, 101, True, 3.5, "10", None])
async def test_invalid_limit_rejected_before_database_access(limit: object):
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await get_full_text_search("python", session, limit=limit)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sql_injection_like_text_is_not_executed(fts_session: AsyncSession):
    await get_full_text_search("python'; DROP TABLE search_index; --", fts_session)

    count = await fts_session.scalar(text("SELECT count(*) FROM search_index"))
    assert count == 8
