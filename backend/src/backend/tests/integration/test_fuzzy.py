"""PostgreSQL integration and validation tests for Developer's Eye fuzzy retrieval.

Expected production contract:
    backend.search.retrieval.fuzzy.get_fuzzy_search(
        query: str, session: AsyncSession, limit: int = 20
    ) -> list[dict[str, int | float]]

Each row must contain:
    {"document_id": int, "fuzzy_score": float}

V1 retrieval contract:
    - fuzzy-match document titles using PostgreSQL pg_trgm word similarity;
    - match against an indexable word-similarity predicate (<%);
    - sort by fuzzy_score DESC, document_id ASC;
    - return at most ``limit`` rows (1..100);
    - strip surrounding whitespace, return [] for blank strings;
    - reject non-string queries and invalid limits before accessing the DB.

The database fixture creates and populates a *temporary* document table on one
connection. It never inserts into the real document table. Use a dedicated DB.

Required setup:
    CREATE DATABASE developers_eye_test;
    -- Connect to developers_eye_test, then:
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

Run from backend/:
    $env:PYTHONPATH = "src"
    $env:TEST_DATABASE_URL = "postgresql+asyncpg://<credentials>@localhost:5432/developers_eye_test"
    poetry run pytest src/backend/tests/integration/test_fuzzy.py -v
"""

from __future__ import annotations

import math
import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.sql.sqltypes import BigInteger, Integer, SmallInteger

from backend.models import Document
from backend.search.retrieval.fuzzy import get_fuzzy_search


TEST_TITLES: tuple[tuple[int, str], ...] = (
    (101, "Python Async Tutorial"),
    (102, "FastAPI Dependency Injection"),
    (103, "JavaScript Promises Guide"),
    (104, "Rust Ownership and Borrowing"),
    (105, "Python Async Tutorial"),  # Deliberate tie with document 101.
    (106, "Python Data Types"),
    (107, "PostgreSQL Full Text Search"),
    (108, "Kubernetes Cluster Setup"),
    (109, "React Hooks Reference"),
    (110, "FastAPI Authentication"),
    (111, "Asyncio Python Guide"),
    (112, "Docker Container Networking"),
)


@pytest_asyncio.fixture
async def fuzzy_session():
    """Run against a temp table, never the real document records."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a separate developers_eye_test database")

    try:
        url = make_url(database_url)
    except Exception as exc:
        pytest.fail(f"TEST_DATABASE_URL is not a valid SQLAlchemy URL: {type(exc).__name__}")

    if url.drivername != "postgresql+asyncpg":
        pytest.fail("TEST_DATABASE_URL must use the postgresql+asyncpg driver")
    if url.database != "developers_eye_test":
        pytest.fail("Safety check: tests require database named developers_eye_test")

    table = Document.__table__
    if table.schema is not None:
        pytest.fail("Document uses an explicit schema; pg_temp shadowing cannot isolate it")
    if "title" not in table.c:
        pytest.fail("Expected Document.title column; adapt the fixture to your model")

    pk = tuple(inspect(Document).primary_key)
    if len(pk) != 1 or not isinstance(pk[0].type, (SmallInteger, Integer, BigInteger)):
        pytest.fail("Test fixture expects one integer primary key on Document")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                present = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')")
                )
                if not present:
                    pytest.fail(
                        "pg_trgm is not installed in developers_eye_test. Run: "
                        "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
                    )

                # SQL identifiers come exclusively from trusted ORM metadata.
                preparer = engine.dialect.identifier_preparer
                table_name = preparer.quote(table.name)
                pk_name = preparer.quote(pk[0].name)
                title_name = preparer.quote(table.c.title.name)

                # Session queries should resolve an unqualified Document model to
                # our temporary table instead of the real table in public.
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(
                    text(
                        f"CREATE TEMP TABLE {table_name} ("
                        f"{pk_name} BIGINT PRIMARY KEY, "
                        f"{title_name} TEXT NOT NULL"
                        ") ON COMMIT DROP"
                    )
                )
                await connection.execute(
                    text(
                        f"CREATE INDEX test_document_title_trgm "
                        f"ON {table_name} USING gin ({title_name} gin_trgm_ops)"
                    )
                )
                # Do not let a local postgres configuration alter the comparison.
                await connection.execute(
                    text("SET LOCAL pg_trgm.word_similarity_threshold = 0.6")
                )

                await connection.execute(
                    text(
                        f"INSERT INTO {table_name} ({pk_name}, {title_name}) "
                        "VALUES (:id, :title)"
                    ),
                    [{"id": doc_id, "title": title} for doc_id, title in TEST_TITLES],
                )

                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
                # Rolling back removes all data and the temporary table.
    finally:
        await engine.dispose()


def assert_fuzzy_rows(rows: list[dict[str, int | float]], limit: int = 20) -> None:
    """Check stable response schema and score ordering."""
    assert isinstance(rows, list)
    assert len(rows) <= limit
    ids = [row["document_id"] for row in rows]
    assert len(ids) == len(set(ids)), "Document IDs must be unique"

    for row in rows:
        assert set(row) == {"document_id", "fuzzy_score"}
        assert type(row["document_id"]) is int
        assert type(row["fuzzy_score"]) is float
        assert math.isfinite(row["fuzzy_score"])
        assert 0.0 <= row["fuzzy_score"] <= 1.0

    for before, after in zip(rows, rows[1:]):
        assert before["fuzzy_score"] >= after["fuzzy_score"]
        if before["fuzzy_score"] == after["fuzzy_score"]:
            assert before["document_id"] < after["document_id"]


@pytest.mark.asyncio
async def test_exact_title_match_has_highest_score(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("Python Async Tutorial", fuzzy_session)
    assert_fuzzy_rows(rows)
    assert [row["document_id"] for row in rows[:2]] == [101, 105]
    assert math.isclose(rows[0]["fuzzy_score"], 1.0, abs_tol=1e-6)
    assert rows[0]["fuzzy_score"] == rows[1]["fuzzy_score"]


@pytest.mark.asyncio
async def test_prefix_typo_finds_fastapi_titles(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("fastap", fuzzy_session)
    assert_fuzzy_rows(rows)
    assert {102, 110}.issubset({row["document_id"] for row in rows})


@pytest.mark.asyncio
async def test_extra_character_typo_finds_python(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("pythonn", fuzzy_session)
    assert_fuzzy_rows(rows)
    assert 101 in {row["document_id"] for row in rows}


@pytest.mark.asyncio
async def test_relevant_title_outscores_less_relevant_title(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("FastAPI Authentication", fuzzy_session)
    assert_fuzzy_rows(rows)
    assert rows[0]["document_id"] == 110
    assert math.isclose(rows[0]["fuzzy_score"], 1.0, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_unrelated_query_returns_no_results(fuzzy_session: AsyncSession):
    assert await get_fuzzy_search("zzzxqvv", fuzzy_session) == []


@pytest.mark.asyncio
async def test_case_insensitive_matching(fuzzy_session: AsyncSession):
    lowercase = await get_fuzzy_search("fastapi", fuzzy_session)
    uppercase = await get_fuzzy_search("FASTAPI", fuzzy_session)
    assert_fuzzy_rows(lowercase)
    assert_fuzzy_rows(uppercase)
    assert lowercase == uppercase


@pytest.mark.asyncio
async def test_trims_outer_whitespace(fuzzy_session: AsyncSession):
    normal = await get_fuzzy_search("fastapi", fuzzy_session)
    padded = await get_fuzzy_search("  fastapi  ", fuzzy_session)
    assert normal == padded


@pytest.mark.asyncio
async def test_limit_one_and_stable_tie_break(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("Python Async Tutorial", fuzzy_session, limit=1)
    assert_fuzzy_rows(rows, limit=1)
    assert [row["document_id"] for row in rows] == [101]


@pytest.mark.asyncio
async def test_limit_is_respected(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("python", fuzzy_session, limit=2)
    assert_fuzzy_rows(rows, limit=2)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_search_never_returns_duplicate_documents(fuzzy_session: AsyncSession):
    rows = await get_fuzzy_search("python", fuzzy_session, limit=100)
    assert_fuzzy_rows(rows, limit=100)
    assert len(rows) == len({row["document_id"] for row in rows})


@pytest.mark.asyncio
async def test_no_table_mutation_from_user_input(fuzzy_session: AsyncSession):
    await get_fuzzy_search("fastapi'; DROP TABLE document; --", fuzzy_session)
    # The ORM's unqualified table name resolves to pg_temp, not public.
    count = await fuzzy_session.scalar(select(func.count()).select_from(Document.__table__))
    assert count == len(TEST_TITLES)


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "  ", " \t \n "])
async def test_blank_query_skips_database(query: str):
    session = AsyncMock(spec=AsyncSession)
    assert await get_fuzzy_search(query, session) == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [None, 12, [], {}])
async def test_non_string_query_rejected_before_database(query: object):
    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(TypeError, match="query must be a string"):
        await get_fuzzy_search(query, session)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1, 101, True, 3.5, "20", None])
async def test_invalid_limit_rejected_before_database(limit: object):
    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        await get_fuzzy_search("python", session, limit=limit)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_error_propagates_to_caller():
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = RuntimeError("temporary database failure")
    with pytest.raises(RuntimeError, match="temporary database failure"):
        await get_fuzzy_search("python", session)
    session.execute.assert_awaited_once()
