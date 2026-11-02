"""Unit tests for rank_candidates, without a live PostgreSQL connection.

Tokenization and statistics I/O are mocked; BM25 calculations, candidate
merging, validation, and final ordering are exercised using real code.
"""

from __future__ import annotations

from math import log
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import backend.search.ranking.orchestrator as orchestrator
from backend.search.query_selector.planner import SearchMode
from backend.search.ranking.statistics import MAX_CANDIDATES
from backend.search.ranking.types import (
    ChannelStatistics,
    CorpusStatistics,
    DocumentStatistics,
    RankingConfig,
)
from backend.search.types import RankedHit, RetrievalHit


CORPUS = CorpusStatistics(document_count=100, average_document_length=100.0)


def make_stats(
    frequencies: dict[int, int], *, term: str = "async"
) -> ChannelStatistics:
    """Build internally consistent candidate stats for one query term."""
    return ChannelStatistics(
        corpus=CORPUS,
        document_frequencies={term: 10},
        documents={
            document_id: DocumentStatistics(
                document_id=document_id,
                document_length=100,
                term_frequencies={term: tf} if tf else {},
            )
            for document_id, tf in frequencies.items()
        },
    )


def reference_bm25(tf: int) -> float:
    """Independent single-term expectation for the fixed fixture corpus."""
    idf = log(1 + (100 - 10 + 0.5) / (10 + 0.5))
    return idf * (tf * (1.2 + 1)) / (tf + 1.2)


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def dependencies(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    tokenizer = AsyncMock(return_value=(("async",), ("async",)))
    statistics_loader = AsyncMock()
    monkeypatch.setattr(orchestrator, "tokenize_query", tokenizer)
    monkeypatch.setattr(orchestrator, "load_channel_statistics", statistics_loader)
    return tokenizer, statistics_loader


@pytest.mark.asyncio
async def test_empty_candidates_skip_database_work(session, dependencies):
    tokenizer, loader = dependencies

    result = await orchestrator.rank_candidates(session, "async", [])

    assert result == []
    tokenizer.assert_not_awaited()
    loader.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   ", None, 123])
async def test_rejects_invalid_query_before_io(session, dependencies, query):
    tokenizer, loader = dependencies

    with pytest.raises(ValueError, match="nonempty string"):
        await orchestrator.rank_candidates(
            session, query, [RetrievalHit(document_id=1)]
        )

    tokenizer.assert_not_awaited()
    loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_mode_scores_only_text_channel(session, dependencies):
    tokenizer, loader = dependencies
    loader.return_value = make_stats({1: 3, 2: 1})

    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        [RetrievalHit(document_id=2), RetrievalHit(document_id=1)],
        mode=" TeXt ",
        text_corpus=CORPUS,
    )

    assert [hit.document_id for hit in ranked] == [1, 2]
    assert ranked[0].score == pytest.approx(reference_bm25(3))
    assert ranked[1].score == pytest.approx(reference_bm25(1))
    assert all(isinstance(hit, RankedHit) for hit in ranked)
    tokenizer.assert_awaited_once_with(session, "async", config=None)
    loader.assert_awaited_once_with(
        session, (1, 2), ("async",), "TEXT", corpus=CORPUS
    )


@pytest.mark.asyncio
async def test_code_mode_scores_only_code_channel(session, dependencies):
    _, loader = dependencies
    loader.return_value = make_stats({1: 1, 2: 4})

    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        [RetrievalHit(document_id=1), RetrievalHit(document_id=2)],
        mode=SearchMode.CODE,
        code_corpus=CORPUS,
    )

    assert [hit.document_id for hit in ranked] == [2, 1]
    assert ranked[0].score == pytest.approx(reference_bm25(4))
    loader.assert_awaited_once_with(
        session, (1, 2), ("async",), "CODE", corpus=CORPUS
    )


@pytest.mark.asyncio
async def test_all_mode_merges_duplicates_and_combines_bm25(session, dependencies):
    tokenizer, loader = dependencies
    text_stats = make_stats({1: 5, 2: 1})
    code_stats = make_stats({1: 1, 2: 4})
    loader.side_effect = (
        lambda _session, ids, terms, mode, *, corpus:
        text_stats if mode == "TEXT" else code_stats
    )

    hits = [
        RetrievalHit(document_id=2, search_rank=0.25),
        RetrievalHit(document_id=1, search_rank=0.40),
        RetrievalHit(document_id=2, search_rank=0.80, code_rank=0.30),
        RetrievalHit(document_id=1, code_rank=0.90),
    ]
    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        iter(hits),
        mode=SearchMode.ALL,
        config=RankingConfig(text_weight=0.5, code_weight=2.0),
        text_corpus=CORPUS,
        code_corpus=CORPUS,
    )

    assert [hit.document_id for hit in ranked] == [2, 1]
    assert ranked[0].score == pytest.approx(
        0.5 * reference_bm25(1) + 2.0 * reference_bm25(4)
    )
    assert ranked[1].score == pytest.approx(
        0.5 * reference_bm25(5) + 2.0 * reference_bm25(1)
    )
    assert (ranked[0].search_rank, ranked[0].code_rank) == (0.80, 0.30)
    assert (ranked[1].search_rank, ranked[1].code_rank) == (0.40, 0.90)
    assert len(ranked) == 2
    assert loader.await_count == 2
    assert [call.args[3] for call in loader.await_args_list] == ["TEXT", "CODE"]
    assert all(call.args[1] == (1, 2) for call in loader.await_args_list)
    tokenizer.assert_awaited_once()


@pytest.mark.asyncio
async def test_equal_bm25_scores_break_ties_by_document_id(session, dependencies):
    _, loader = dependencies
    loader.return_value = make_stats({9: 2, 3: 2, 5: 2})

    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        [RetrievalHit(document_id=i) for i in (9, 3, 5)],
        mode="text",
        text_corpus=CORPUS,
    )

    assert [hit.document_id for hit in ranked] == [3, 5, 9]
    assert len({hit.score for hit in ranked}) == 1


@pytest.mark.asyncio
async def test_missing_indexed_documents_are_excluded(session, dependencies):
    _, loader = dependencies
    loader.return_value = make_stats({1: 2})

    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        [RetrievalHit(document_id=1), RetrievalHit(document_id=2)],
        mode="text",
        text_corpus=CORPUS,
    )

    assert [hit.document_id for hit in ranked] == [1]


@pytest.mark.asyncio
async def test_no_positive_terms_skips_statistics_loading(session, dependencies):
    tokenizer, loader = dependencies
    tokenizer.return_value = ((), ("async",))

    ranked = await orchestrator.rank_candidates(
        session,
        "NOT async",
        [RetrievalHit(document_id=1)],
        mode="text",
        text_corpus=CORPUS,
    )

    assert ranked == []
    loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_mode_skips_zero_weight_channel(session, dependencies):
    _, loader = dependencies
    loader.return_value = make_stats({1: 2})

    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        [RetrievalHit(document_id=1)],
        config=RankingConfig(text_weight=0, code_weight=2),
        code_corpus=CORPUS,
    )

    assert ranked[0].score == pytest.approx(2 * reference_bm25(2))
    loader.assert_awaited_once_with(
        session, (1,), ("async",), "CODE", corpus=CORPUS
    )


@pytest.mark.asyncio
async def test_single_mode_ignores_channel_fusion_weights(session, dependencies):
    _, loader = dependencies
    loader.return_value = make_stats({1: 2})

    ranked = await orchestrator.rank_candidates(
        session,
        "async",
        [RetrievalHit(document_id=1)],
        mode="text",
        config=RankingConfig(text_weight=0, code_weight=10),
        text_corpus=CORPUS,
    )

    assert ranked[0].score == pytest.approx(reference_bm25(2))
    loader.assert_awaited_once()


@pytest.mark.asyncio
async def test_active_channel_requires_precomputed_corpus(session, dependencies):
    tokenizer, loader = dependencies

    with pytest.raises(ValueError, match="text_corpus"):
        await orchestrator.rank_candidates(
            session, "async", [RetrievalHit(document_id=1)], mode="text"
        )

    tokenizer.assert_not_awaited()
    loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_excess_candidates_fail_before_database_work(session, dependencies):
    tokenizer, loader = dependencies
    hits = (RetrievalHit(document_id=i) for i in range(1, MAX_CANDIDATES + 2))

    with pytest.raises(ValueError, match="unique candidates"):
        await orchestrator.rank_candidates(session, "async", hits)

    tokenizer.assert_not_awaited()
    loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_loader_error_propagates(session, dependencies):
    _, loader = dependencies
    loader.side_effect = RuntimeError("statistics database unavailable")

    with pytest.raises(RuntimeError, match="statistics database unavailable"):
        await orchestrator.rank_candidates(
            session,
            "async",
            [RetrievalHit(document_id=1)],
            mode="text",
            text_corpus=CORPUS,
        )


@pytest.mark.asyncio
async def test_nonfinite_combined_score_is_rejected(
    session, dependencies, monkeypatch: pytest.MonkeyPatch
):
    _, loader = dependencies
    loader.return_value = make_stats({1: 2})
    monkeypatch.setattr(
        orchestrator, "apply_BM25", lambda stats, terms, parameters: {1: float("nan")}
    )

    with pytest.raises(ValueError, match="invalid combined score"):
        await orchestrator.rank_candidates(
            session,
            "async",
            [RetrievalHit(document_id=1)],
            mode="text",
            text_corpus=CORPUS,
        )
