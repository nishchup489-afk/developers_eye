"""Regression tests for exact-lexeme BM25 statistics.

Requires PostgreSQL and TEST_DATABASE_URL pointing to an isolated test database.
Creates a temporary search_index table, so persistent tables are never changed.

From backend/:
    poetry run pytest tests/integration/test_ranking_statistics.py -v
"""

from __future__ import annotations

import os
from math import log1p

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.search.ranking.bm25 import apply_BM25
from backend.search.ranking.statistics import (
    _get_candidate_documents,
    _get_document_frequencies,
    get_corpus_statistics,
    load_channel_statistics,
)
from backend.search.ranking.types import BM25Parameters
from backend.search.tokenizer import tokenize_query


# ID, English-language document, literal code-oriented content.
DOCUMENTS = (
    (1, "universe universe running", "universe run"),
    (2, "universe python", "univers"),
    (3, "univ python", "univ"),
    (4, "running running", "running"),
    (5, "the and or", ""),  # English stopwords yield an empty text vector.
    (6, "", ""),            # Both vectors empty.
)


@pytest_asyncio.fixture
async def db_session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL test database")
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must use postgresql+asyncpg://")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                # Shadow the real search_index on this connection only.
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
                    text("CREATE INDEX test_rank_text_gin ON search_index USING GIN (search_vector)")
                )
                await connection.execute(
                    text("CREATE INDEX test_rank_code_gin ON search_index USING GIN (code_vector)")
                )

                for doc_id, body, code in DOCUMENTS:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO search_index
                                (document_id, search_vector, code_vector)
                            VALUES (
                                :doc_id,
                                to_tsvector('english', :body),
                                to_tsvector('simple', :code)
                            )
                            """
                        ),
                        {"doc_id": doc_id, "body": body, "code": code},
                    )

                async with AsyncSession(
                    bind=connection, expire_on_commit=False
                ) as session:
                    yield session
                # Transaction rolls back; no persistent rows are modified.
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_universe_is_stemmed_once_by_postgresql(db_session: AsyncSession):
    text_terms, code_terms = await tokenize_query(db_session, "universe")

    assert text_terms == ("univers",)
    assert code_terms == ("universe",)

    # The regression: DF must count 'univers', not re-stem it to 'univ'.
    assert await _get_document_frequencies(
        db_session, text_terms, "TEXT"
    ) == {"univers": 2}

    # Code uses the 'simple' configuration and remains unstemmed.
    assert await _get_document_frequencies(
        db_session, code_terms, "CODE"
    ) == {"universe": 1}


@pytest.mark.asyncio
async def test_df_matches_exact_lexemes_not_double_stems(db_session: AsyncSession):
    actual = await _get_document_frequencies(
        db_session, ("univers", "univ", "run", "missing"), "TEXT"
    )

    assert actual == {
        "univers": 2,  # Documents 1 and 2.
        "univ": 1,     # Document 3 only.
        "run": 2,      # Documents 1 and 4.
        "missing": 0,
    }

    # This reproduces the old bug on a deterministic miniature corpus.
    old_df = await db_session.scalar(
        text(
            """
            SELECT count(*)
            FROM search_index
            WHERE search_vector @@ plainto_tsquery('english', 'univers')
            """
        )
    )
    assert old_df == 1
    assert actual["univers"] != old_df


@pytest.mark.asyncio
async def test_text_and_code_have_independent_df(db_session: AsyncSession):
    assert await _get_document_frequencies(
        db_session, ("univers", "univ"), "TEXT"
    ) == {"univers": 2, "univ": 1}

    assert await _get_document_frequencies(
        db_session, ("univers", "univ", "universe"), "CODE"
    ) == {"univers": 1, "univ": 1, "universe": 1}

    assert await _get_document_frequencies(db_session, (), "TEXT") == {}


@pytest.mark.asyncio
async def test_tf_and_dl_use_exact_indexed_positions(db_session: AsyncSession):
    docs = await _get_candidate_documents(
        db_session, (1, 2, 3, 4, 5, 6), ("univers", "univ", "run"), "TEXT"
    )

    assert set(docs) == {1, 2, 3, 4, 5, 6}
    assert docs[1].document_length == 3
    assert dict(docs[1].term_frequencies) == {"univers": 2, "run": 1}
    assert docs[2].document_length == 2
    assert dict(docs[2].term_frequencies) == {"univers": 1}
    assert docs[3].document_length == 2
    assert dict(docs[3].term_frequencies) == {"univ": 1}
    assert docs[4].document_length == 2
    assert dict(docs[4].term_frequencies) == {"run": 2}

    for document_id in (5, 6):
        assert docs[document_id].document_length == 0
        assert dict(docs[document_id].term_frequencies) == {}


@pytest.mark.asyncio
async def test_channel_corpus_counts_and_average_lengths(db_session: AsyncSession):
    text_corpus = await get_corpus_statistics(db_session, "TEXT")
    code_corpus = await get_corpus_statistics(db_session, "CODE")

    assert text_corpus.document_count == 6
    assert text_corpus.average_document_length == pytest.approx(9 / 6)
    assert code_corpus.document_count == 6
    assert code_corpus.average_document_length == pytest.approx(5 / 6)


@pytest.mark.asyncio
async def test_fixed_df_flows_into_bm25(db_session: AsyncSession):
    corpus = await get_corpus_statistics(db_session, "TEXT")
    stats = await load_channel_statistics(
        db_session,
        (1, 2, 3),
        ("univers",),
        "TEXT",
        corpus=corpus,
    )

    assert stats.document_frequencies["univers"] == 2
    assert stats.documents[1].term_frequencies["univers"] == 2
    assert stats.documents[2].term_frequencies["univers"] == 1

    scores = apply_BM25(stats, ("univers",), BM25Parameters())
    idf = log1p((6 - 2 + 0.5) / (2 + 0.5))

    def expected(tf: int, dl: int) -> float:
        return idf * (tf * 2.2) / (
            tf + 1.2 * (0.25 + 0.75 * dl / 1.5)
        )

    assert scores[1] == pytest.approx(expected(tf=2, dl=3))
    assert scores[2] == pytest.approx(expected(tf=1, dl=2))
    assert scores[3] == 0
    assert scores[1] > scores[2] > scores[3]


def _tsvector_literal(term: str) -> str:
    """Encode one exact lexeme in PostgreSQL's TSVECTOR input syntax."""
    return "'" + term.replace("\\", "\\\\").replace("'", "''") + "':1"


@pytest.mark.asyncio
@pytest.mark.parametrize("lexeme", ["o'reilly", r"slash\\path"])
async def test_exact_lexeme_query_handles_quoting(
    db_session: AsyncSession, lexeme: str
):
    # Construct a literal indexed lexeme rather than relying on text parsing.
    await db_session.execute(
        text(
            """
            INSERT INTO search_index (document_id, search_vector, code_vector)
            VALUES (
                7,
                to_tsvector('english', ''),
                CAST(:vector AS tsvector)
            )
            """
        ),
        {"vector": _tsvector_literal(lexeme)},
    )

    assert await _get_document_frequencies(
        db_session, (lexeme,), "CODE"
    ) == {lexeme: 1}
