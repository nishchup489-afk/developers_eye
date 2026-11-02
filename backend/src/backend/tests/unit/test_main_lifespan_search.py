"""Verify BM25 corpus scans run at startup rather than per search."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

import backend.main as main
import backend.search.service as service
from backend.search.ranking.types import CorpusStatistics


@pytest.mark.asyncio
async def test_startup_loads_both_corpus_snapshots(monkeypatch):
    calls = []
    corpus = CorpusStatistics(document_count=10, average_document_length=20)

    @asynccontextmanager
    async def session_factory():
        yield object()

    async def fake_statistics(session, mode):
        calls.append(mode)
        return corpus

    fake_engine = type("Engine", (), {"dispose": AsyncMock()})()
    monkeypatch.setattr(main, "SessionFactory", session_factory)
    monkeypatch.setattr(main, "get_corpus_statistics", fake_statistics)
    monkeypatch.setattr(main, "engine", fake_engine)

    async with main.lifespan(main.app):
        assert calls == ["TEXT", "CODE"]
        assert service._corpus_snapshots is not None
        assert service._corpus_snapshots.text.document_count == 10
    assert service._corpus_snapshots is None
    fake_engine.dispose.assert_awaited_once()
