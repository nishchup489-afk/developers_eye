"""Title-match candidate channel (EXP-0017).

Requires TEST_DATABASE_URL; a temporary search_index shadows the real one.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.search.retrieval.fts import search_text
from backend.search.retrieval.titles import search_titles

BODY_HEAVY = " ".join(["javascript optional chaining operator explained"] * 40)

# id, title (weight A), body (weight D), category
DOCUMENTS = (
    (1, "Optional chaining - JavaScript | MDN", "The ?. operator reads a property.", "docs"),
    (2, "Operators cheat sheet", BODY_HEAVY, "articles"),
    (3, "Operator reference", BODY_HEAVY, "articles"),
    (4, "Optional chaining in Django templates", "javascript is not used here", "docs"),
    (5, "Chaining promises - JavaScript", "optional then calls", "docs"),
    (6, "Unrelated title", "javascript optional chaining", "docs"),
)


@pytest_asyncio.fixture
async def session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(text(
                    "CREATE TEMP TABLE search_index (document_id BIGINT PRIMARY KEY, "
                    "search_vector TSVECTOR NOT NULL, category TEXT NOT NULL) ON COMMIT DROP"
                ))
                for doc_id, title, body, category in DOCUMENTS:
                    await connection.execute(text(
                        "INSERT INTO search_index VALUES (:id, "
                        "setweight(to_tsvector('english', :title), 'A') || "
                        "setweight(to_tsvector('english', :body), 'D'), :category)"
                    ), {"id": doc_id, "title": title, "body": body, "category": category})
                async with AsyncSession(bind=connection) as s:
                    yield s
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reference_page_is_crowded_out_of_a_small_text_pool(session):
    # The defect: body repetition wins the weighted ts_rank pool.
    top = await search_text(session, "javascript optional chaining", limit=2)
    assert 1 not in {hit.document_id for hit in top}


@pytest.mark.asyncio
async def test_title_channel_returns_the_page_whose_title_is_the_query(session):
    hits = await search_titles(session, "javascript optional chaining", limit=3)
    ids = [hit.document_id for hit in hits]
    assert ids[0] == 1                       # all three lexemes in the title
    assert 6 not in ids                      # no query word in its title
    assert 2 not in ids and 3 not in ids     # under half of the lexemes in the title
    assert hits[0].search_rank == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_title_channel_keeps_websearch_semantics_and_filters(session):
    assert 1 not in {h.document_id for h in await search_titles(session, "optional chaining -javascript")}
    assert [h.document_id for h in await search_titles(session, "django optional chaining")] == [4]
    in_articles = await search_titles(session, "javascript optional chaining", categories=("articles",))
    assert {h.document_id for h in in_articles} <= {2, 3}
    assert await search_titles(session, "zzznotaword") == []
    assert await search_titles(session, "   ") == []


@pytest.mark.asyncio
async def test_title_channel_validates_input(session):
    with pytest.raises(TypeError):
        await search_titles(session, None)
    with pytest.raises(ValueError):
        await search_titles(session, "x" * 257)
    with pytest.raises(ValueError):
        await search_titles(session, "python", limit=0)
