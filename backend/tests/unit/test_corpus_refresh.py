
"""Unit tests for BM25 corpus snapshot refresh behavior."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

import backend.main as main
import backend.search.service as service
from backend.search.ranking.types import CorpusStatistics


@pytest.fixture(autouse=True)
def clear_snapshots():
    service.clear_corpus_statistics()
    yield
    service.clear_corpus_statistics()


@pytest.mark.asyncio
async def test_failed_refresh_does_not_replace_either_snapshot(monkeypatch):
    original = CorpusStatistics(document_count=10, average_document_length=5)
    service.set_corpus_statistics(original, original)

    @asynccontextmanager
    async def fake_factory():
        yield object()

    async def incomplete_load(_session, mode):
        if mode == "CODE":
            raise RuntimeError("code corpus timed out")
        return CorpusStatistics(document_count=11, average_document_length=7)

    monkeypatch.setattr(main, "SessionFactory", fake_factory)
    monkeypatch.setattr(main, "get_corpus_statistics", incomplete_load)

    with pytest.raises(RuntimeError, match="timed out"):
        await main.load_corpus_statistics()

    assert service._corpus_snapshots is not None
    assert service._corpus_snapshots.text is original
    assert service._corpus_snapshots.code is original


@pytest.mark.asyncio
async def test_successful_refresh_replaces_both_snapshots(monkeypatch):
    old = CorpusStatistics(document_count=2, average_document_length=1)
    service.set_corpus_statistics(old, old)

    @asynccontextmanager
    async def fake_factory():
        yield object()

    async def load(_session, mode):
        return CorpusStatistics(
            document_count=5,
            average_document_length=3 if mode == "TEXT" else 4,
        )

    monkeypatch.setattr(main, "SessionFactory", fake_factory)
    monkeypatch.setattr(main, "get_corpus_statistics", load)

    await main.load_corpus_statistics()

    assert service._corpus_snapshots is not None
    assert service._corpus_snapshots.text.document_count == 5
    assert service._corpus_snapshots.text.average_document_length == 3
    assert service._corpus_snapshots.code.document_count == 5
    assert service._corpus_snapshots.code.average_document_length == 4


@pytest.mark.asyncio
async def test_background_refresh_retries_after_failure(monkeypatch):
    original = CorpusStatistics(document_count=3, average_document_length=2)
    service.set_corpus_statistics(original, original)

    attempts = 0
    sleeps = 0

    async def broken_refresh():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("database temporarily unavailable")

    async def no_delay(_seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(main, "load_corpus_statistics", broken_refresh)
    monkeypatch.setattr(main.asyncio, "sleep", no_delay)

    with pytest.raises(asyncio.CancelledError):
        await main.refresh_corpus_statistics()

    assert attempts >= 2, (
        "A transient refresh error must not terminate the refresh loop"
    )
    assert service._corpus_snapshots is not None
    assert service._corpus_snapshots.text is original
    assert service._corpus_snapshots.code is original
