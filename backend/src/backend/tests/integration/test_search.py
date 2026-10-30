"""PostgreSQL integration tests for the public search service.

Like test_fts.py, these shadow ``document`` and ``search_index`` with
temporary tables, so no production rows are touched.

Requires TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test
    poetry run pytest src/backend/tests/integration/test_search.py -v
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.search.service import categorize, search_documents

DOCUMENTS = [
    # id, url, type, title, description, body, tags, available
    (1, "https://fastapi.tiangolo.com/async/", "documentation", "Concurrency and async",
     "Async in FastAPI", "Use async def for path operations that await database calls.",
     ["python", "fastapi"], True),
    (2, "https://github.com/fastapi/fastapi/issues/42", "issue", "Async session leak",
     None, "An async session leaks when the request is cancelled.", ["fastapi"], True),
    (3, "https://stackoverflow.com/questions/1/async", "question", "How does async work?",
     None, "Explain async and await in Python.", [], True),
    (4, "https://example.com/gone", "blog", "Async removed page",
     None, "Async content that disappeared.", [], False),
    (5, "https://realpython.com/async-io-python/", "tutorial", "Async IO in Python",
     None, "A walkthrough of async IO.", "not-a-list", True),
]


@pytest_asyncio.fixture
async def search_session():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database to run search integration tests")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(text(
                    """
                    CREATE TEMP TABLE document (
                        id BIGINT PRIMARY KEY,
                        canonical_url TEXT NOT NULL,
                        document_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        body TEXT,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        is_available BOOLEAN NOT NULL DEFAULT true
                    ) ON COMMIT DROP
                    """
                ))
                await connection.execute(text(
                    """
                    CREATE TEMP TABLE search_index (
                        document_id BIGINT PRIMARY KEY,
                        search_vector TSVECTOR NOT NULL,
                        code_vector TSVECTOR NOT NULL
                    ) ON COMMIT DROP
                    """
                ))
                for doc_id, url, kind, title, description, body, tags, available in DOCUMENTS:
                    await connection.execute(
                        text(
                            "INSERT INTO document VALUES (:id, :url, :kind, :title, :description,"
                            " :body, CAST(:metadata AS jsonb), :available)"
                        ),
                        {"id": doc_id, "url": url, "kind": kind, "title": title,
                         "description": description, "body": body,
                         "metadata": json.dumps({"tags": tags}), "available": available},
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO search_index VALUES (:id,"
                            " to_tsvector('english', :title || ' ' || :body), to_tsvector('simple', ''))"
                        ),
                        {"id": doc_id, "title": title, "body": body},
                    )
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
    finally:
        await engine.dispose()


async def test_returns_frontend_shaped_results(search_session: AsyncSession):
    results = await search_documents(search_session, "async")

    assert {r.url for r in results} == {
        "https://fastapi.tiangolo.com/async/",
        "https://github.com/fastapi/fastapi/issues/42",
        "https://stackoverflow.com/questions/1/async",
        "https://realpython.com/async-io-python/",
    }
    by_url = {r.url: r for r in results}
    docs = by_url["https://fastapi.tiangolo.com/async/"]
    assert docs.source == "docs" and docs.type == "documentation"
    assert docs.tags == ["python", "fastapi"]
    assert "async" in docs.snippet.lower() and "<b>" not in docs.snippet
    assert by_url["https://realpython.com/async-io-python/"].tags == []
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True) and all(s > 0 for s in scores)


async def test_unavailable_documents_are_hidden(search_session: AsyncSession):
    results = await search_documents(search_session, "disappeared")
    assert results == []


async def test_category_filter_and_limit(search_session: AsyncSession):
    github = await search_documents(search_session, "async", category="github")
    assert [r.url for r in github] == ["https://github.com/fastapi/fastapi/issues/42"]

    assert len(await search_documents(search_session, "async", limit=2)) == 2


async def test_no_match_returns_empty(search_session: AsyncSession):
    assert await search_documents(search_session, "kubernetes") == []


@pytest.mark.parametrize(
    ("url", "kind", "expected"),
    [
        ("https://docs.github.com/en/actions", "documentation", "github"),
        ("https://gitlab.com/a/b", "repository", "github"),
        ("https://unix.stackexchange.com/q/1", "question", "stackoverflow"),
        ("https://old.reddit.com/r/python/x", "discussion", "reddit"),
        ("https://leetcode.com/problems/two-sum/", "other", "practice"),
        ("https://pycon.org/2026/", "event", "events"),
        ("https://docs.python.org/3/", "documentation", "docs"),
        ("https://blog.example.com/post", "blog", "articles"),
        ("https://example.com/x", "other", "articles"),
        ("https://notgithub.com/x", "blog", "articles"),
    ],
)
def test_categorize(url: str, kind: str, expected: str):
    assert categorize(url, kind) == expected
