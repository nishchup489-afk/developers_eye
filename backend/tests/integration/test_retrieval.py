"""PostgreSQL integration tests for retrieving BM25 statistics from search_index.

backend/search/ranking/statistics.py reads document frequency (DF), term
frequency (TF) and document length (DL) straight from the TSVECTOR columns.
test_ranking_statistics.py covers stemming, corpus averages and the BM25 flow;
this file covers the retrieval edges: lexemes no document has, IDs that are
not indexed, empty vectors, the single-document helpers, the no-candidate
shortcut and input validation. Every expected number is worked out by hand.

Like test_fts.py, the production search_index table is shadowed by a temporary
table on one transaction-bound connection; nothing outside it is touched.

Requires:
    TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test

Run from backend/:
    poetry run pytest tests/integration/test_retrieval.py -v
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.models import SearchIndex
from backend.search.ranking.statistics import (
    _get_candidate_documents,
    _get_document_frequencies,
    _get_document_length,
    _get_term_frequency,
    load_channel_statistics,
)
from backend.search.ranking.types import CorpusStatistics

# (document_id, english body, simple code). Words are chosen so the English
# stem equals the word itself: python, async, web, rust.
DOCUMENTS = [
    (1, "python async python", ""),           # text: python=2 async=1, DL 3; code DL 0
    (2, "python web", "async def main"),      # text: python=1 web=1, DL 2; code DL 3
    (3, "rust", "async async"),               # text: rust=1, DL 1;          code async=2, DL 2
]


@pytest_asyncio.fixture
async def stats_session():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database to run retrieval tests")
    if not database_url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must use the postgresql+asyncpg driver")
    if SearchIndex.__table__.schema is not None:
        pytest.fail("SearchIndex declares an explicit schema; pg_temp cannot shadow its table.")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(text(
                    """
                    CREATE TEMP TABLE search_index (
                        document_id BIGINT PRIMARY KEY,
                        search_vector TSVECTOR NOT NULL,
                        code_vector TSVECTOR NOT NULL
                    ) ON COMMIT DROP
                    """
                ))
                for document_id, body, code in DOCUMENTS:
                    await connection.execute(
                        text(
                            "INSERT INTO search_index VALUES "
                            "(:id, to_tsvector('english', :body), to_tsvector('simple', :code))"
                        ),
                        {"id": document_id, "body": body, "code": code},
                    )
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_document_frequencies_in_one_query(stats_session):
    """DF per lexeme, with 0 for a lexeme no document contains."""
    assert await _get_document_frequencies(
        stats_session, ["python", "async", "web", "missing"], "TEXT"
    ) == {"python": 2, "async": 1, "web": 1, "missing": 0}
    assert await _get_document_frequencies(stats_session, ["async", "python"], "CODE") == {
        "async": 2, "python": 0,
    }
    assert await _get_document_frequencies(stats_session, [], "TEXT") == {}


@pytest.mark.asyncio
async def test_candidate_term_frequencies_and_lengths(stats_session):
    """TF counts positions; DL sums all positions; unknown IDs are left out."""
    docs = await _get_candidate_documents(stats_session, [1, 2, 3, 99], ["python", "async"], "TEXT")

    assert set(docs) == {1, 2, 3}
    assert (docs[1].document_length, dict(docs[1].term_frequencies)) == (3, {"python": 2, "async": 1})
    assert (docs[2].document_length, dict(docs[2].term_frequencies)) == (2, {"python": 1})
    assert (docs[3].document_length, dict(docs[3].term_frequencies)) == (1, {})


@pytest.mark.asyncio
async def test_code_channel_reads_code_vector(stats_session):
    """CODE mode reads code_vector; an empty code vector has length 0."""
    docs = await _get_candidate_documents(stats_session, [1, 3], ["async"], "CODE")

    assert (docs[1].document_length, dict(docs[1].term_frequencies)) == (0, {})
    assert (docs[3].document_length, dict(docs[3].term_frequencies)) == (2, {"async": 2})


@pytest.mark.asyncio
async def test_single_document_helpers(stats_session):
    assert await _get_term_frequency(stats_session, 1, "python", "TEXT") == 2
    assert await _get_term_frequency(stats_session, 3, "python", "TEXT") == 0
    assert await _get_term_frequency(stats_session, 99, "python", "TEXT") is None
    assert await _get_document_length(stats_session, 2, "CODE") == 3
    assert await _get_document_length(stats_session, 99, "CODE") is None


@pytest.mark.asyncio
async def test_load_channel_statistics_without_candidates_skips_queries(stats_session):
    corpus = CorpusStatistics(document_count=3, average_document_length=2.0)
    stats = await load_channel_statistics(stats_session, [], ["python"], "TEXT", corpus=corpus)

    assert stats.corpus is corpus
    assert dict(stats.documents) == {} and dict(stats.document_frequencies) == {}


@pytest.mark.asyncio
async def test_load_channel_statistics_validates_inputs(stats_session):
    corpus = CorpusStatistics(document_count=3, average_document_length=2.0)
    with pytest.raises(TypeError, match="CorpusStatistics"):
        await load_channel_statistics(stats_session, [1], ["python"], "TEXT", corpus=None)
    with pytest.raises(ValueError, match="TEXT or CODE"):
        await load_channel_statistics(stats_session, [1], ["python"], "ALL", corpus=corpus)
    with pytest.raises(ValueError, match="lexeme"):
        await load_channel_statistics(stats_session, [1], ["python async"], "TEXT", corpus=corpus)
