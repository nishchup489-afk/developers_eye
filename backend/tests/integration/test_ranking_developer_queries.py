"""PostgreSQL-backed developer-query and multi-term BM25 regression tests.

Install in: backend/tests/integration/test_ranking_developer_queries.py
Run from backend/:
    poetry run pytest tests/integration/test_ranking_developer_queries.py -v -rs

Requires TEST_DATABASE_URL=postgresql+asyncpg://.../developers_eye_test.
The tests shadow search_index using a temporary table on one connection;
no persistent search_index rows are inserted or changed.

Scope:
* English multi-term BM25 with independently calculated expected scores.
* Code-query scoring of underscores, dotted identifiers, camelCase, and numbers.
* Deduplication of repeated query terms.
* Weighted TEXT/CODE fusion in ALL mode.

The intent is scoring correctness for the actual PostgreSQL tokenization,
not proof that an exact identifier gets an extra ranking boost. PostgreSQL
might split a dotted identifier into multiple indexed lexemes. Tests check
that terms returned by the tokenizer are scored consistently with the index.
"""

from __future__ import annotations

import os
from math import log1p

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.search.ranking.orchestrator import rank_candidates
from backend.search.ranking.statistics import (
    _get_document_frequencies,
    get_corpus_statistics,
    load_channel_statistics,
)
from backend.search.ranking.types import RankingConfig
from backend.search.retrieval.code import search_code
from backend.search.retrieval.fts import search_text
from backend.search.tokenizer import tokenize_query
from backend.search.types import RetrievalHit


# Fixed test population: document_id, text body, code content.
# Shorter/longer and repeated/single representations are deliberate.
DOCUMENTS = (
    (1, "python async database python async database", ""),
    (2, "python async database", ""),
    (3, "python async guide", ""),
    (4, "python database tutorial", ""),
    (5, "javascript browser render", "unrelated"),
    (6, "asyncio guide", "asyncio.create_task asyncio.create_task"),
    (7, "asyncio guide", "asyncio.create_task"),
    (8, "constructor guide", "__init__ __init__"),
    (9, "constructor guide", "__init__"),
    (10, "lookup documentation", "get_user_by_id get_user_by_id"),
    (11, "lookup documentation", "get_user_by_id"),
    (12, "react lifecycle", "useEffect useEffect"),
    (13, "react lifecycle", "useEffect"),
    (14, "http response guide", "HTTP 404 HTTP 404"),
    (15, "http response guide", "HTTP 404"),
    (16, "python async guide", "python async"),
    (17, "python async", "python async python async"),
    (18, "", ""),
)


@pytest_asyncio.fixture
async def ranking_session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database")
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must use the postgresql+asyncpg driver")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(
                    text(
                        """
                        CREATE TEMP TABLE search_index (
                            document_id BIGINT PRIMARY KEY,
                            search_vector TSVECTOR NOT NULL,
                            code_vector TSVECTOR NOT NULL,
                            category TEXT NOT NULL DEFAULT 'articles'
                        ) ON COMMIT DROP
                        """
                    )
                )
                await connection.execute(
                    text(
                        "CREATE INDEX test_devquery_text_gin "
                        "ON search_index USING GIN (search_vector)"
                    )
                )
                await connection.execute(
                    text(
                        "CREATE INDEX test_devquery_code_gin "
                        "ON search_index USING GIN (code_vector)"
                    )
                )

                for document_id, body, code in DOCUMENTS:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO search_index
                                (document_id, search_vector, code_vector)
                            VALUES (
                                :id,
                                to_tsvector('english', :body),
                                to_tsvector('simple', :code)
                            )
                            """
                        ),
                        {"id": document_id, "body": body, "code": code},
                    )

                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    yield session
    finally:
        await engine.dispose()


def expected_bm25(*, N: int, df: int, tf: int, dl: int, avgdl: float) -> float:
    """Independent BM25 reference with production default k1=1.2, b=0.75."""
    if tf == 0:
        return 0.0
    k1, b = 1.2, 0.75
    idf = log1p((N - df + 0.5) / (df + 0.5))
    return idf * (tf * (k1 + 1)) / (
        tf + k1 * (1 - b + b * dl / avgdl)
    )


@pytest.mark.asyncio
async def test_multi_term_text_query_scores_all_terms(ranking_session: AsyncSession):
    """Two occurrences of each search term outrank one occurrence of each."""
    query = "python async database"
    text_terms, _ = await tokenize_query(ranking_session, query)
    assert text_terms == ("python", "async", "databas")

    hits = await search_text(ranking_session, query)
    assert {hit.document_id for hit in hits} == {1, 2}

    corpus = await get_corpus_statistics(ranking_session, "TEXT")
    assert corpus.document_count == len(DOCUMENTS)

    # Counts are from the fixed full corpus, not only the two candidates.
    df = await _get_document_frequencies(ranking_session, text_terms, "TEXT")
    assert df == {"python": 6, "async": 5, "databas": 3}

    ranked = await rank_candidates(
        ranking_session, query, hits, mode="text", text_corpus=corpus
    )
    assert [hit.document_id for hit in ranked] == [1, 2]

    # Exact, independent expected score for each fixed document.
    expected_1 = sum(
        expected_bm25(
            N=len(DOCUMENTS), df=df[term], tf=2, dl=6,
            avgdl=corpus.average_document_length,
        )
        for term in text_terms
    )
    expected_2 = sum(
        expected_bm25(
            N=len(DOCUMENTS), df=df[term], tf=1, dl=3,
            avgdl=corpus.average_document_length,
        )
        for term in text_terms
    )

    assert ranked[0].score == pytest.approx(expected_1)
    assert ranked[1].score == pytest.approx(expected_2)
    assert expected_1 > expected_2 > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "repeated_id", "single_id"),
    [
        ("asyncio.create_task", 6, 7),  # dotted module.function
        ("__init__", 8, 9),             # Python dunder method
        ("get_user_by_id", 10, 11),     # snake_case identifier
        ("useEffect", 12, 13),          # camelCase React hook
        ("HTTP 404", 14, 15),           # mixed letters and numbers
    ],
)
async def test_identifier_queries_score_repeat_above_single(
    ranking_session: AsyncSession,
    query: str,
    repeated_id: int,
    single_id: int,
):
    """Use real PostgreSQL tokenizer/retrieval, then real CODE BM25 scoring."""
    _, code_terms = await tokenize_query(ranking_session, query)
    assert code_terms, f"PostgreSQL tokenized {query!r} to no CODE terms"
    assert len(code_terms) == len(set(code_terms))

    retrieved = await search_code(ranking_session, query)
    retrieved_ids = {hit.document_id for hit in retrieved}
    assert {repeated_id, single_id} <= retrieved_ids, (
        f"CODE retrieval did not match both {query!r} fixtures; "
        f"terms={code_terms!r}; retrieved={sorted(retrieved_ids)}"
    )

    # Select only the paired documents to isolate the scoring assertion;
    # the DF remains corpus-wide across ALL documents.
    hits = [
        RetrievalHit(document_id=hit.document_id, code_rank=hit.score)
        for hit in retrieved
        if hit.document_id in {repeated_id, single_id}
    ]
    corpus = await get_corpus_statistics(ranking_session, "CODE")
    df = await _get_document_frequencies(ranking_session, code_terms, "CODE")
    assert all(count >= 2 for count in df.values())

    ranked = await rank_candidates(
        ranking_session, query, hits, mode="code", code_corpus=corpus
    )
    assert [hit.document_id for hit in ranked] == [repeated_id, single_id], (
        f"Unexpected CODE BM25 ordering for {query!r} with terms={code_terms!r}"
    )
    assert ranked[0].score > ranked[1].score > 0

    # Check the score mathematically, not just the ordering.
    stats = await load_channel_statistics(
        ranking_session,
        (repeated_id, single_id),
        code_terms,
        "CODE",
        corpus=corpus,
    )
    for hit in ranked:
        doc = stats.documents[hit.document_id]
        reference = sum(
            expected_bm25(
                N=corpus.document_count,
                df=stats.document_frequencies[term],
                tf=doc.term_frequencies.get(term, 0),
                dl=doc.document_length,
                avgdl=corpus.average_document_length,
            )
            for term in code_terms
        )
        assert hit.score == pytest.approx(reference)


@pytest.mark.asyncio
async def test_repeating_a_query_identifier_does_not_double_count_bm25(
    ranking_session: AsyncSession,
):
    query = "get_user_by_id"
    candidates = [RetrievalHit(document_id=10), RetrievalHit(document_id=11)]
    corpus = await get_corpus_statistics(ranking_session, "CODE")

    once = await rank_candidates(
        ranking_session, query, candidates, mode="code", code_corpus=corpus
    )
    twice = await rank_candidates(
        ranking_session, f"{query} {query}", candidates,
        mode="code", code_corpus=corpus,
    )
    assert [hit.document_id for hit in once] == [10, 11]
    assert [hit.document_id for hit in twice] == [10, 11]
    assert [hit.score for hit in twice] == pytest.approx(
        [hit.score for hit in once]
    )


@pytest.mark.asyncio
async def test_all_mode_weighted_fusion_for_multi_term_query(
    ranking_session: AsyncSession,
):
    query = "python async"
    ids = (1, 16, 17)
    candidates = [RetrievalHit(document_id=i) for i in ids]
    text_corpus = await get_corpus_statistics(ranking_session, "TEXT")
    code_corpus = await get_corpus_statistics(ranking_session, "CODE")

    text_ranked = await rank_candidates(
        ranking_session, query, candidates, mode="text", text_corpus=text_corpus
    )
    code_ranked = await rank_candidates(
        ranking_session, query, candidates, mode="code", code_corpus=code_corpus
    )
    all_ranked = await rank_candidates(
        ranking_session,
        query,
        candidates,
        mode="all",
        text_corpus=text_corpus,
        code_corpus=code_corpus,
        config=RankingConfig(text_weight=0.3, code_weight=1.7),
    )

    text_scores = {hit.document_id: hit.score for hit in text_ranked}
    code_scores = {hit.document_id: hit.score for hit in code_ranked}
    all_scores = {hit.document_id: hit.score for hit in all_ranked}

    assert set(text_scores) == set(code_scores) == set(all_scores) == set(ids)
    assert all(score > 0 for score in text_scores.values())
    assert code_scores[1] == 0.0  # Only a TEXT match.
    assert code_scores[16] > 0 and code_scores[17] > 0

    for document_id in ids:
        assert all_scores[document_id] == pytest.approx(
            0.3 * text_scores[document_id] + 1.7 * code_scores[document_id]
        )
    assert [hit.document_id for hit in all_ranked] == sorted(
        ids, key=lambda i: (-all_scores[i], i)
    )
