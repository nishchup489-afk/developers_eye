"""Developer's Eye: end-to-end golden search contract.

Install as backend/tests/golden/test_golden_search_final.py.
Run from backend/ with TEST_DATABASE_URL pointing to a DEDICATED database
whose name ends in `_test` or starts with `test_`:

    poetry run pytest tests/golden/test_golden_search_final.py -v -rs

Uses transaction-scoped temporary search_index tables. No production
search_index rows are read or written. No corpus crawler is needed.

Scope: exact current unweighted BM25 mathematics, PostgreSQL TF/DF/DL/avgDL/N,
TEXT/CODE/ALL scoring, boolean query semantics, A/B/C/D storage, new weighted
`ts_rank` candidate selection, >100-candidate cutoff, and index mutations.
This is NOT an evaluation of human relevance or BM25F.
"""

from __future__ import annotations

import os
from math import log1p
from typing import Final

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.search.merge import merge_hits
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

# Exact PostgreSQL tsvector input literals. Positions (and A/B/C weights) are
# frozen so changing parsing/stemming cannot silently move the golden baseline.
# IDs 2 and 10 deliberately have identical TF/DL but different field weights.
VECTORS: Final[tuple[tuple[int, str, str], ...]] = (
    (1, "'python':1A,3C 'async':2B 'databas':4C", "'python':1A 'async':2B"),
    (2, "'python':1C 'async':2C 'databas':3C", "'python':1C 'async':2C 'databas':3C"),
    (3, "'python':1C 'async':2C", "'python':1C 'async':2C"),
    (4, "'python':1C 'databas':2C", "'python':1C 'databas':2C"),
    (5, "'async':1C 'databas':2C", "'async':1C 'databas':2C"),
    (6, "'javascript':1A 'fetch':2A 'exampl':3B", "'javascript':1C 'fetch':2C 'examples':3C"),
    (7, "'javascript':1C,2C 'fetch':3C,4C 'exampl':5C", "'javascript':1C,2C 'fetch':3C,4C 'examples':5C"),
    (8, "", "'useeffect':1A,2B"),
    (9, "", ""),
    (10, "'python':1A 'async':2B 'databas':3C", "'python':1A 'async':2B 'databas':3C"),
)

N: Final = 10
AVG_DL: Final = 2.4
GOLDEN_QUERY: Final = "python async database"
GOLDEN_TERMS: Final = ("python", "async", "databas")
GOLDEN_ORDER: Final = (1, 2, 10)
GOLDEN_SCORES: Final = {
    1: 1.8918227559643621,
    2: 1.8865036666786141,
    10: 1.8865036666786141,
}


def reference_bm25(*, N: int, df: int, tf: int, dl: int, avgdl: float) -> float:
    """Independent textbook BM25 reference. Never import production formula."""
    if not tf:
        return 0.0
    k1, b = 1.2, 0.75
    idf = log1p((N - df + 0.5) / (df + 0.5))
    return idf * ((k1 + 1) * tf) / (tf + k1 * (1 - b + b * dl / avgdl))


@pytest_asyncio.fixture
async def session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a dedicated PostgreSQL test database")
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("TEST_DATABASE_URL must use postgresql+asyncpg://")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                dbname = await connection.scalar(text("SELECT current_database()"))
                if not isinstance(dbname, str) or not (
                    dbname.lower().endswith("_test") or dbname.lower().startswith("test_")
                ):
                    pytest.fail(
                        "Refusing database whose name does not end in '_test' "
                        "or start with 'test_'. Use a dedicated test database."
                    )
                await connection.execute(text("SET LOCAL search_path TO pg_temp, public"))
                await connection.execute(text("""
                    CREATE TEMP TABLE search_index (
                        document_id BIGINT PRIMARY KEY,
                        search_vector TSVECTOR NOT NULL,
                        code_vector TSVECTOR NOT NULL,
                        category TEXT NOT NULL DEFAULT 'articles'
                    ) ON COMMIT DROP
                """))
                await connection.execute(text("""
                    CREATE INDEX golden_text_gin
                    ON search_index USING GIN (search_vector)
                """))
                await connection.execute(text("""
                    CREATE INDEX golden_code_gin
                    ON search_index USING GIN (code_vector)
                """))
                async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                    for document_id, text_vec, code_vec in VECTORS:
                        await db.execute(text("""
                            INSERT INTO search_index
                                (document_id, search_vector, code_vector)
                            VALUES (:id, CAST(:tv AS tsvector), CAST(:cv AS tsvector))
                        """), {"id": document_id, "tv": text_vec, "cv": code_vec})
                    yield db
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_golden_postgres_corpus_statistics(session: AsyncSession):
    text_corpus = await get_corpus_statistics(session, "TEXT")
    code_corpus = await get_corpus_statistics(session, "CODE")
    assert text_corpus.document_count == code_corpus.document_count == N
    assert text_corpus.average_document_length == pytest.approx(AVG_DL)
    assert code_corpus.average_document_length == pytest.approx(AVG_DL)

    df = await _get_document_frequencies(session, GOLDEN_TERMS, "TEXT")
    assert df == {"python": 5, "async": 5, "databas": 5}

    docs = await load_channel_statistics(
        session, (1, 2, 3, 9, 10), GOLDEN_TERMS, "TEXT", corpus=text_corpus
    )
    assert (docs.documents[1].document_length, dict(docs.documents[1].term_frequencies)) == (
        4, {"python": 2, "async": 1, "databas": 1}
    )
    assert (docs.documents[2].document_length, dict(docs.documents[2].term_frequencies)) == (
        3, {"python": 1, "async": 1, "databas": 1}
    )
    assert docs.documents[9].document_length == 0
    assert not docs.documents[9].term_frequencies
    assert dict(docs.documents[10].term_frequencies) == dict(docs.documents[2].term_frequencies)


@pytest.mark.asyncio
async def test_golden_exact_text_bm25_and_order(session: AsyncSession):
    terms, _ = await tokenize_query(session, GOLDEN_QUERY)
    assert terms == GOLDEN_TERMS
    hits = await search_text(session, GOLDEN_QUERY, limit=100)
    assert {h.document_id for h in hits} == set(GOLDEN_ORDER)

    corpus = await get_corpus_statistics(session, "TEXT")
    ranked = await rank_candidates(
        session, GOLDEN_QUERY, list(reversed(hits)),
        mode="text", text_corpus=corpus
    )
    assert tuple(h.document_id for h in ranked) == GOLDEN_ORDER
    for hit in ranked:
        assert hit.score == pytest.approx(GOLDEN_SCORES[hit.document_id], rel=1e-11, abs=1e-11)

    # Cross-check frozen scores against a reference written independently of production.
    assert GOLDEN_SCORES[1] == pytest.approx(
        reference_bm25(N=N, df=5, tf=2, dl=4, avgdl=AVG_DL)
        + 2 * reference_bm25(N=N, df=5, tf=1, dl=4, avgdl=AVG_DL)
    )
    assert GOLDEN_SCORES[2] == pytest.approx(
        3 * reference_bm25(N=N, df=5, tf=1, dl=3, avgdl=AVG_DL)
    )


@pytest.mark.asyncio
async def test_golden_current_bm25_does_not_apply_field_weights(session: AsyncSession):
    """Freeze the known limitation; replace with separate BM25F golden tests later."""
    corpus = await get_corpus_statistics(session, "TEXT")
    ranked = await rank_candidates(
        session,
        GOLDEN_QUERY,
        [RetrievalHit(document_id=10), RetrievalHit(document_id=2)],
        mode="text",
        text_corpus=corpus,
    )
    # 10 has A/B terms; 2 is all C. Current BM25 deliberately ignores the weights.
    assert [h.document_id for h in ranked] == [2, 10]
    assert ranked[0].score == pytest.approx(ranked[1].score)


@pytest.mark.asyncio
async def test_golden_code_identifier_and_empty_results(session: AsyncSession):
    text_terms, code_terms = await tokenize_query(session, "useEffect")
    assert text_terms == ("useeffect",)
    assert code_terms == ("useeffect",)
    hits = await search_code(session, "useEffect")
    assert [h.document_id for h in hits] == [8]
    corpus = await get_corpus_statistics(session, "CODE")
    ranked = await rank_candidates(
        session, "useEffect",
        [RetrievalHit(document_id=8, code_rank=hits[0].score)],
        mode="code", code_corpus=corpus,
    )
    assert [h.document_id for h in ranked] == [8]
    assert ranked[0].score == pytest.approx(
        reference_bm25(N=N, df=1, tf=2, dl=2, avgdl=AVG_DL)
    )
    assert await search_text(session, "missingnomatchterm") == []
    assert await search_code(session, "missingnomatchterm") == []


@pytest.mark.asyncio
async def test_golden_boolean_or_exclusion_and_phrase(session: AsyncSession):
    assert {h.document_id for h in await search_text(session, "python OR javascript")} == {
        1, 2, 3, 4, 6, 7, 10
    }
    assert [h.document_id for h in await search_text(session, "python -async")] == [4]
    assert {h.document_id for h in await search_text(session, '"javascript fetch"')} == {6, 7}


@pytest.mark.asyncio
async def test_golden_all_mode_fusion_is_exact(session: AsyncSession):
    query = "python async"
    text_hits = await search_text(session, query)
    code_hits = await search_code(session, query)
    assert {h.document_id for h in text_hits} == {1, 2, 3, 10}
    assert {h.document_id for h in code_hits} == {1, 2, 3, 10}
    merged = merge_hits(
        text_hits,
        [RetrievalHit(document_id=h.document_id, code_rank=h.score) for h in code_hits],
    )
    assert len(merged) == 4
    tcorpus = await get_corpus_statistics(session, "TEXT")
    ccorpus = await get_corpus_statistics(session, "CODE")
    config = RankingConfig(text_weight=0.5, code_weight=1.5)
    actual = await rank_candidates(
        session, query, merged, mode="all", config=config,
        text_corpus=tcorpus, code_corpus=ccorpus,
    )
    tstats = await load_channel_statistics(
        session, (1, 2, 3, 10), ("python", "async"), "TEXT", corpus=tcorpus
    )
    cstats = await load_channel_statistics(
        session, (1, 2, 3, 10), ("python", "async"), "CODE", corpus=ccorpus
    )

    def independent_channel_score(doc_id: int, channel) -> float:
        document = channel.documents[doc_id]
        return sum(
            reference_bm25(
                N=channel.corpus.document_count,
                df=channel.document_frequencies[term],
                tf=document.term_frequencies.get(term, 0),
                dl=document.document_length,
                avgdl=channel.corpus.average_document_length,
            )
            for term in ("python", "async")
        )

    expected = {
        doc_id: (
            0.5 * independent_channel_score(doc_id, tstats)
            + 1.5 * independent_channel_score(doc_id, cstats)
        )
        for doc_id in (1, 2, 3, 10)
    }
    assert [h.document_id for h in actual] == sorted(
        expected, key=lambda i: (-expected[i], i)
    )
    for hit in actual:
        assert hit.score == pytest.approx(expected[hit.document_id], rel=1e-10)


@pytest.mark.asyncio
async def test_golden_weighted_ts_rank_candidate_cutoff(session: AsyncSession):
    """Golden contract for the new weighted ts_rank, normalization=1 retriever."""
    # Add 120 matched body-only distractors; the A-weight title page must win.
    await session.execute(text("""
        INSERT INTO search_index (document_id, search_vector, code_vector)
        VALUES (300,
          CAST(:title_vec AS tsvector), ''::tsvector)
    """), {"title_vec": "'javascript':1A 'fetch':2A 'exampl':3A"})
    await session.execute(text("""
        INSERT INTO search_index (document_id, search_vector, code_vector)
        SELECT n, CAST(:body_vec AS tsvector), ''::tsvector
        FROM generate_series(301, 420) AS n
    """), {"body_vec": "'javascript':1C 'fetch':2C 'exampl':3C"})

    query = "javascript fetch examples"
    matches = await search_text(session, query, limit=100)
    ids = [h.document_id for h in matches]
    assert len(ids) == len(set(ids)) == 100
    assert ids[0] == 300

    # Independently evaluate the contractual PostgreSQL expression. This also
    # detects accidental reversion to ts_rank_cd/default weights/normalization.
    sql = text("""
        WITH q AS (
            SELECT websearch_to_tsquery('english', :query) AS tsq
        )
        SELECT si.document_id,
            ts_rank(
                ARRAY[0.05, 0.10, 0.35, 1.0]::real[],
                si.search_vector, q.tsq, 1
            ) AS score
        FROM search_index si CROSS JOIN q
        WHERE si.search_vector @@ q.tsq
        ORDER BY score DESC, si.document_id ASC
        LIMIT 100
    """)
    expected = (await session.execute(sql, {"query": query})).all()
    assert ids == [int(row.document_id) for row in expected]
    for actual, row in zip(matches, expected, strict=True):
        assert actual.search_rank == pytest.approx(float(row.score), rel=1e-6, abs=1e-7)


@pytest.mark.asyncio
async def test_golden_mutations_recalculate_tf_df_dl_and_order(session: AsyncSession):
    """Independent transaction-local insert/update/delete coverage."""
    before = await get_corpus_statistics(session, "TEXT")
    assert before.document_count == 10
    assert (await _get_document_frequencies(session, ("databas",), "TEXT")) == {
        "databas": 5
    }

    # Upsert-like update removes a term: 2 must disappear from 3-term retrieval.
    await session.execute(text("""
        UPDATE search_index SET search_vector = CAST(:tv AS tsvector)
        WHERE document_id = 2
    """), {"tv": "'python':1C 'async':2C"})
    assert (await _get_document_frequencies(session, ("databas",), "TEXT")) == {
        "databas": 4
    }
    assert {h.document_id for h in await search_text(session, GOLDEN_QUERY)} == {1, 10}

    await session.execute(text("DELETE FROM search_index WHERE document_id = 10"))
    assert (await _get_document_frequencies(session, ("databas",), "TEXT")) == {
        "databas": 3
    }
    mid = await get_corpus_statistics(session, "TEXT")
    assert mid.document_count == 9
    assert {h.document_id for h in await search_text(session, GOLDEN_QUERY)} == {1}

    await session.execute(text("""
        INSERT INTO search_index (document_id, search_vector, code_vector)
        VALUES (11, CAST(:tv AS tsvector), ''::tsvector)
    """), {"tv": "'python':1A 'async':2B 'databas':3C"})
    final = await get_corpus_statistics(session, "TEXT")
    assert final.document_count == 10
    assert (await _get_document_frequencies(session, ("databas",), "TEXT")) == {
        "databas": 4
    }
    hits = await search_text(session, GOLDEN_QUERY)
    assert {h.document_id for h in hits} == {1, 11}
    stats = await load_channel_statistics(
        session, (1, 11), GOLDEN_TERMS, "TEXT", corpus=final
    )
    ranked = await rank_candidates(
        session, GOLDEN_QUERY, hits, mode="text", text_corpus=final
    )
    for hit in ranked:
        doc = stats.documents[hit.document_id]
        expected = sum(
            reference_bm25(
                N=final.document_count,
                df=stats.document_frequencies[term],
                tf=doc.term_frequencies.get(term, 0),
                dl=doc.document_length,
                avgdl=final.average_document_length,
            )
            for term in GOLDEN_TERMS
        )
        assert hit.score == pytest.approx(expected, rel=1e-10)
