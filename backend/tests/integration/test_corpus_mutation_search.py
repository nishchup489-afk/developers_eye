
"""Integration tests for BM25 while search_index grows and shrinks.

Run from backend/:

    poetry run pytest tests/integration/test_corpus_mutation_search.py -v -rs

Requires TEST_DATABASE_URL pointing to an isolated PostgreSQL test database.

Temporary document and search_index tables shadow the real tables.
Tests cover deterministic mutations between search requests, not
simultaneous multi-connection indexing and searching.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from math import isfinite

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.api import search as search_api
from backend.main import app
from backend.search import service
from backend.search.ranking.statistics import (
    _get_document_frequencies,
    get_corpus_statistics,
    load_channel_statistics,
)


@pytest_asyncio.fixture
async def search_session():
    url = os.environ.get("TEST_DATABASE_URL")

    if not url:
        pytest.skip(
            "Set TEST_DATABASE_URL to an isolated PostgreSQL test database"
        )

    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail(
            "TEST_DATABASE_URL must use postgresql+asyncpg://"
        )

    engine = create_async_engine(url, pool_pre_ping=True)

    try:
        async with engine.connect() as connection:
            async with connection.begin():

                await connection.execute(
                    text("SET LOCAL search_path TO pg_temp, public")
                )

                await connection.execute(text("""
                    CREATE TEMP TABLE document (
                        id BIGINT PRIMARY KEY,
                        canonical_url TEXT NOT NULL,
                        document_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        body TEXT,
                        content_hash TEXT,
                        last_seen_at TIMESTAMPTZ DEFAULT now(),
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        is_available BOOLEAN NOT NULL DEFAULT true
                    ) ON COMMIT DROP
                """))

                await connection.execute(text("""
                    CREATE TEMP TABLE search_index (
                        document_id BIGINT PRIMARY KEY,
                        search_vector TSVECTOR NOT NULL,
                        code_vector TSVECTOR NOT NULL,
                        category TEXT NOT NULL DEFAULT 'docs'
                    ) ON COMMIT DROP
                """))

                await connection.execute(text("""
                    CREATE INDEX test_growth_text_gin
                    ON search_index USING GIN (search_vector)
                """))

                await connection.execute(text("""
                    CREATE INDEX test_growth_code_gin
                    ON search_index USING GIN (code_vector)
                """))

                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                ) as session:
                    try:
                        yield session
                    finally:
                        service.clear_corpus_statistics()

    finally:
        await engine.dispose()


async def add_document(
    session: AsyncSession,
    document_id: int,
    body: str,
) -> None:

    await session.execute(
        text("""
            INSERT INTO document (
                id,
                canonical_url,
                document_type,
                title,
                body,
                metadata,
                is_available
            )
            VALUES (
                :id,
                :url,
                'documentation',
                :title,
                :body,
                '{}'::jsonb,
                true
            )
        """),
        {
            "id": document_id,
            "url": f"https://example.org/{document_id}",
            "title": f"Document {document_id}",
            "body": body,
        },
    )

    await session.execute(
        text("""
            INSERT INTO search_index (
                document_id,
                search_vector,
                code_vector,
                category
            )
            VALUES (
                :id,
                to_tsvector('english', :body),
                to_tsvector('simple', :body),
                'docs'
            )
        """),
        {
            "id": document_id,
            "body": body,
        },
    )


async def remove_document(
    session: AsyncSession,
    document_id: int,
) -> None:

    await session.execute(
        text("""
            DELETE FROM search_index
            WHERE document_id = :id
        """),
        {"id": document_id},
    )

    await session.execute(
        text("""
            DELETE FROM document
            WHERE id = :id
        """),
        {"id": document_id},
    )


async def install_snapshot(
    session: AsyncSession,
) -> None:

    text_corpus = await get_corpus_statistics(
        session,
        "TEXT",
    )

    code_corpus = await get_corpus_statistics(
        session,
        "CODE",
    )

    service.set_corpus_statistics(
        text_corpus,
        code_corpus,
    )


def result_ids(results: list) -> set[int]:
    return {
        int(result.url.rsplit("/", 1)[-1])
        for result in results
    }


# ---------------------------------------------------------
# TEST 1: Index grows beyond cached N
# ---------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["text", "code", "all"])
async def test_search_after_index_growth_exceeds_cached_n(
    search_session: AsyncSession,
    mode: str,
):

    await add_document(
        search_session,
        1,
        "python tutorial",
    )

    await add_document(
        search_session,
        2,
        "rust ownership",
    )

    await install_snapshot(search_session)

    assert service._corpus_snapshots is not None

    cached = service._corpus_snapshots.text

    assert cached.document_count == 2

    before = await service.search_documents(
        search_session,
        "python",
        mode=mode,
    )

    assert result_ids(before) == {1}

    for document_id in (3, 4, 5):
        await add_document(
            search_session,
            document_id,
            "python python programming",
        )

    live_df = await _get_document_frequencies(
        search_session,
        ("python",),
        "TEXT",
    )

    assert live_df["python"] == 4
    assert live_df["python"] > cached.document_count

    ranked = await service.search_documents(
        search_session,
        "python",
        mode=mode,
    )

    assert result_ids(ranked) == {1, 3, 4, 5}

    assert all(
        isfinite(result.score) and result.score > 0
        for result in ranked
    )

    stats = await load_channel_statistics(
        search_session,
        (1, 3, 4, 5),
        ("python",),
        "TEXT",
        corpus=cached,
    )

    assert (
        stats.corpus.document_count
        >= live_df["python"]
    )

    assert (
        stats.corpus.document_count
        >= len(stats.documents)
    )

    await install_snapshot(search_session)

    assert (
        service._corpus_snapshots.text.document_count
        == 5
    )

    refreshed = await service.search_documents(
        search_session,
        "python",
        mode=mode,
    )

    assert result_ids(refreshed) == {1, 3, 4, 5}


# ---------------------------------------------------------
# TEST 2: Index shrinks and removed docs disappear
# ---------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["text", "code", "all"])
async def test_search_after_index_shrink_drops_removed_documents(
    search_session: AsyncSession,
    mode: str,
):

    for document_id in range(1, 6):
        await add_document(
            search_session,
            document_id,
            "python reference",
        )

    await install_snapshot(search_session)

    assert service._corpus_snapshots is not None

    assert (
        service._corpus_snapshots.text.document_count
        == 5
    )

    for document_id in (2, 3, 4, 5):
        await remove_document(
            search_session,
            document_id,
        )

    live_df = await _get_document_frequencies(
        search_session,
        ("python",),
        "TEXT",
    )

    assert live_df == {"python": 1}

    results = await service.search_documents(
        search_session,
        "python",
        mode=mode,
    )

    assert result_ids(results) == {1}

    assert all(
        isfinite(result.score) and result.score > 0
        for result in results
    )

    await remove_document(search_session, 1)

    empty_results = await service.search_documents(
        search_session,
        "python",
        mode=mode,
    )

    assert empty_results == []

    await install_snapshot(search_session)

    assert service._corpus_snapshots is not None

    assert (
        service._corpus_snapshots.text.document_count
        == 0
    )

    assert (
        service._corpus_snapshots.text.average_document_length
        == 0
    )


# ---------------------------------------------------------
# TEST 3: Index grows from an empty cached corpus
# ---------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["text", "code", "all"])
async def test_search_after_growth_from_cached_empty_corpus(
    search_session: AsyncSession,
    mode: str,
):

    await install_snapshot(search_session)

    assert service._corpus_snapshots is not None

    assert (
        service._corpus_snapshots.text.document_count
        == 0
    )

    assert (
        service._corpus_snapshots.text.average_document_length
        == 0
    )

    await add_document(
        search_session,
        42,
        "python indexing guide",
    )

    results = await service.search_documents(
        search_session,
        "python",
        mode=mode,
    )

    assert result_ids(results) == {42}

    assert len(results) == 1

    assert isfinite(results[0].score)
    assert results[0].score > 0


# ---------------------------------------------------------
# TEST 4: HTTP API must not return misleading 422
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_http_search_does_not_return_422_for_stale_corpus(
    search_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):

    await add_document(
        search_session,
        1,
        "python docs",
    )

    await install_snapshot(search_session)

    await add_document(
        search_session,
        2,
        "python docs",
    )

    await add_document(
        search_session,
        3,
        "python docs",
    )

    @asynccontextmanager
    async def test_session_factory():
        yield search_session

    monkeypatch.setattr(
        search_api,
        "SessionFactory",
        test_session_factory,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:

        response = await client.get(
            "/search",
            params={
                "q": "python",
                "mode": "text",
            },
        )

    assert response.status_code == 200, response.text

    urls = {
        item["url"]
        for item in response.json()["results"]
    }

    assert urls == {
        "https://example.org/1",
        "https://example.org/2",
        "https://example.org/3",
    }
