"""Unit tests for the new service pipeline. Database I/O is stubbed.

Run from backend/: poetry run pytest tests/unit/test_search_pipeline.py -v
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import backend.search.service as service
from backend.search.query_selector.planner import SearchMode
from backend.search.ranking.types import CorpusStatistics
from backend.search.types import RankedHit, RetrievalHit
from backend.search.retrieval.code import CodeRetrievalHit


@pytest.fixture(autouse=True)
def corpus():
    text = CorpusStatistics(document_count=100, average_document_length=50)
    code = CorpusStatistics(document_count=100, average_document_length=40)
    service.set_corpus_statistics(text, code)
    yield
    service.clear_corpus_statistics()


def meta(id, url, *, document_type="documentation", available=True,
         title=None, description="Fallback description", metadata=None):
    return SimpleNamespace(
        id=id,
        canonical_url=url,
        document_type=document_type,
        title=title or f"Result {id}",
        description=description,
        metadata_={"tags": ["python"], "code_blocks": ["async def example():"]}
        if metadata is None else metadata,
    )


class FakeExecuteResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


def setup_session(metadata=(), bodies=()):
    session = AsyncMock()
    session.execute.side_effect = [
        FakeExecuteResult(metadata),
        FakeExecuteResult(bodies),
    ]
    return session


def replace_dependencies(monkeypatch, *, text=(), code=(), ranked=()):
    txt = AsyncMock(return_value=list(text))
    cod = AsyncMock(return_value=list(code))
    rank = AsyncMock(return_value=list(ranked))
    monkeypatch.setattr(service, "search_text", txt)
    monkeypatch.setattr(service, "search_code", cod)
    monkeypatch.setattr(service, "rank_candidates", rank)
    return txt, cod, rank


@pytest.mark.asyncio
async def test_all_mode_merges_candidates_preserves_scores_and_generates_snippets(monkeypatch):
    txt, cod, rank = replace_dependencies(
        monkeypatch,
        text=[RetrievalHit(document_id=1, search_rank=0.6)],
        code=[CodeRetrievalHit(document_id=1, score=0.9)],
        ranked=[RankedHit(document_id=1, score=2.34567)],
    )
    session = setup_session(
        metadata=[meta(1, "https://docs.python.org/3/", title="Async Python")],
        bodies=[SimpleNamespace(id=1, body="Python async syntax allows awaiting operations.")],
    )
    result = await service.search_documents(session, "  python   async  ")
    assert len(result) == 1
    assert result[0].source == "docs"
    assert "async" in result[0].snippet.lower()
    assert result[0].score == 2.34567
    assert result[0].tags == ["python"]
    text_hits = rank.await_args.args[2]
    assert len(text_hits) == 1
    assert text_hits[0] == RetrievalHit(document_id=1, search_rank=0.6, code_rank=0.9)
    assert rank.await_args.kwargs["text_corpus"].document_count == 100
    assert txt.await_args.args[1] == "python async"
    cod.assert_awaited_once()


@pytest.mark.asyncio
async def test_text_mode_does_not_query_code(monkeypatch):
    txt, cod, rank = replace_dependencies(
        monkeypatch,
        text=[RetrievalHit(document_id=3, search_rank=0.4)],
        ranked=[RankedHit(document_id=3, score=1.0)],
    )
    session = setup_session(
        metadata=[meta(3, "https://example.org/3")],
        bodies=[SimpleNamespace(id=3, body="How Python works")],
    )
    result = await service.search_documents(session, "Python", mode="text")
    assert len(result) == 1
    cod.assert_not_awaited()
    assert rank.await_args.kwargs["mode"] is SearchMode.TEXT


@pytest.mark.asyncio
async def test_code_mode_does_not_query_text_and_uses_code_block(monkeypatch):
    txt, cod, rank = replace_dependencies(
        monkeypatch,
        code=[CodeRetrievalHit(document_id=3, score=0.9)],
        ranked=[RankedHit(document_id=3, score=5.0)],
    )
    session = setup_session(
        metadata=[meta(3, "https://example.org/code")],
        bodies=[SimpleNamespace(id=3, body="This body contains no code")],
    )
    result = await service.search_documents(session, "async", mode="code")
    assert len(result) == 1
    assert "async def" in result[0].snippet
    txt.assert_not_awaited()
    assert rank.await_args.kwargs["mode"] is SearchMode.CODE


@pytest.mark.asyncio
async def test_filter_before_pagination_and_preserve_bm25_order(monkeypatch):
    ranked = [
        RankedHit(document_id=1, score=9),
        RankedHit(document_id=2, score=8),
        RankedHit(document_id=3, score=7),
        RankedHit(document_id=4, score=6),
    ]
    replace_dependencies(
        monkeypatch,
        text=[RetrievalHit(document_id=i, search_rank=1) for i in range(1, 5)],
        ranked=ranked,
    )
    session = setup_session(
        metadata=[
            meta(1, "https://notgithub.org/docs"),
            meta(2, "https://github.com/owner/repo", document_type="issue"),
            meta(3, "https://github.com/owner/repo2", document_type="issue"),
            meta(4, "https://github.com/owner/repo3", document_type="issue"),
        ],
        bodies=[SimpleNamespace(id=3, body="Python explanation")],
    )
    result = await service.search_documents(
        session, "Python", category="github", page=2, limit=1, mode="text"
    )
    assert [r.url for r in result] == ["https://github.com/owner/repo2"]
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_unavailable_and_invalid_urls_removed_before_paging(monkeypatch):
    replace_dependencies(
        monkeypatch,
        text=[RetrievalHit(document_id=i, search_rank=1) for i in (1, 2, 3)],
        ranked=[RankedHit(document_id=i, score=float(4-i)) for i in (1, 2, 3)],
    )
    # Document 2 is unavailable and consequently not returned by the SELECT.
    session = setup_session(
        metadata=[meta(1, "file:///etc/passwd"), meta(3, "https://valid.example/post")],
        bodies=[SimpleNamespace(id=3, body="Relevant Python guidance")],
    )
    result = await service.search_documents(session, "Python", limit=1, mode="text")
    assert [r.url for r in result] == ["https://valid.example/post"]


@pytest.mark.asyncio
async def test_no_hits_skips_bm25_and_metadata(monkeypatch):
    txt, cod, rank = replace_dependencies(monkeypatch)
    session = AsyncMock()
    assert await service.search_documents(session, "nope") == []
    rank.assert_not_awaited()
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_pagination_rejected_without_db_access(monkeypatch):
    replace_dependencies(monkeypatch)
    session = AsyncMock()
    for kwargs in ({"page": 0}, {"page": True}, {"limit": 0}, {"limit": True},
                   {"page": 1000, "limit": 20}):
        with pytest.raises(ValueError):
            await service.search_documents(session, "python", **kwargs)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_uninitialized_stats_rejected_with_nonempty_retrieval(monkeypatch):
    replace_dependencies(monkeypatch,
        text=[RetrievalHit(document_id=1, search_rank=1)])
    service.clear_corpus_statistics()
    with pytest.raises(RuntimeError, match="corpus statistics not initialized"):
        await service.search_documents(AsyncMock(), "python", mode="text")


def test_source_category_host_must_match_domain_boundary():
    assert service.categorize("https://notgithub.com/x", "blog") == "articles"
    assert service.categorize("https://docs.github.com/en/actions", "documentation") == "github"
    assert service.categorize("https://stackoverflow.com/questions/1", "question") == "stackoverflow"


@pytest.mark.asyncio
async def test_no_eligible_metadata_skips_body_and_snippet(monkeypatch):
    replace_dependencies(
        monkeypatch,
        text=[RetrievalHit(document_id=1, search_rank=1)],
        ranked=[RankedHit(document_id=1, score=1.5)],
    )
    session = AsyncMock()
    session.execute.return_value = FakeExecuteResult([])
    result = await service.search_documents(session, "python", mode="text")
    assert result == []
    session.execute.assert_awaited_once()
