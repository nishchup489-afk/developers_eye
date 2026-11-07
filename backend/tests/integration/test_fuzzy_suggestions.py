"""PostgreSQL integration tests for GET /search/suggest's correction logic.

The vocabulary is built the way the indexer builds it: from the lexemes of
to_tsvector('english', ...), so it holds stems such as "configur" and
"librari". These tests check, against PostgreSQL's real english_stem and
pg_trgm, that suggestions come back as readable words and that correctly
spelled words are left alone.

The production search_terms table is shadowed by a temporary table on one
transaction-bound connection; nothing outside it is touched.

Requires:
    TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test  (pg_trgm installed)

Run from backend/:
    poetry run pytest tests/integration/test_fuzzy_suggestions.py -v
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.models.search_terms import SearchTerm
from backend.search.retrieval.fuzzy.candidates import english_stems
from backend.search.retrieval.fuzzy.correction import suggest_query_correction

CORPUS = (
    "Configure the library configuration for Python. "
    "Database queries, caching and asynchronous requests in FastAPI."
)


@pytest_asyncio.fixture
async def session():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database to run suggestion tests")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must use the postgresql+asyncpg driver")
    if SearchTerm.__table__.schema is not None:
        pytest.fail("SearchTerm declares an explicit schema; pg_temp cannot shadow its table.")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(text(
                    "CREATE TEMP TABLE search_terms ("
                    " term TEXT PRIMARY KEY, document_frequency INTEGER NOT NULL"
                    ") ON COMMIT DROP"
                ))
                await connection.execute(text(
                    "INSERT INTO search_terms "
                    "SELECT lexeme, 3 FROM unnest(to_tsvector('english', :corpus))"
                ), {"corpus": CORPUS})
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
    finally:
        await engine.dispose()


async def test_vocabulary_holds_stems(session):
    terms = set((await session.scalars(text("SELECT term FROM search_terms"))).all())
    assert {"configur", "librari", "python", "cach"} <= terms
    assert "configuration" not in terms


async def test_english_stems_matches_the_index(session):
    stems = await english_stems(["Configuration", "libraries", "python", "the"], session)
    assert stems == {
        "configuration": "configur",
        "libraries": "librari",
        "python": "python",
        "the": None,
    }


@pytest.mark.parametrize(("typed", "expected"), [
    ("configuraton", "configuration"),
    ("libary", "library"),
    ("pyhton", "python"),
    ("databse", "database"),
    ("fastapi configuraton", "fastapi configuration"),
])
async def test_typo_suggests_a_real_word(session, typed, expected):
    result = await suggest_query_correction(typed, session)
    assert result.suggested_query == expected
    for correction in result.corrections:
        assert correction.replacement not in {"configur", "librari", "databas"}


@pytest.mark.parametrize("typed", ["configuration", "libraries", "caching", "python"])
async def test_correct_words_are_left_alone(session, typed):
    result = await suggest_query_correction(typed, session)
    assert not result.changed
    assert result.corrections == []
