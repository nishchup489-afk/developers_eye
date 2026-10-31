"""Unit tests for the service/writer orchestration (no live database)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from indexer import service, writer
from indexer.config import IndexerConfig
from indexer.schemas import IndexCandidate, IndexStatus
from indexer.vector import SearchVectors
from sqlalchemy import literal

NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)


class FakeSession:
    def __init__(self):
        self.began = False
        self.ended = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.ended = True

    def begin(self):
        self.began = True
        return self


def fake_session_factory():
    return FakeSession()


def vectors():
    return SearchVectors(
        document_id=1,
        source_id=7,
        source_updated_at=NOW,
        text_vector=literal("dummy"),
        code_vector=literal("dummy"),
    )


def source(**changes):
    x = dict(document_id=1, source_id=7, is_available=True, updated_at=NOW)
    x.update(changes)
    return SimpleNamespace(**x)


def stored(**changes):
    x = dict(indexed_hash="v1:" + "a" * 64, indexed_at=NOW + timedelta(seconds=2))
    x.update(changes)
    return SimpleNamespace(**x)


@pytest.mark.asyncio
async def test_writer_new_index(monkeypatch):
    monkeypatch.setattr(writer, "lock_vocabulary", AsyncMock())
    monkeypatch.setattr(writer, "get_index_lexemes", AsyncMock(return_value=("python",)))
    mock_sync = AsyncMock()
    monkeypatch.setattr(writer, "synchronize_vocabulary", mock_sync)
    mock_lock = AsyncMock(return_value=source())
    mock_read = AsyncMock(return_value=None)
    mock_upsert = AsyncMock(return_value=1)
    monkeypatch.setattr(writer, "get_document_for_update", mock_lock)
    monkeypatch.setattr(writer, "get_search_index", mock_read)
    monkeypatch.setattr(writer, "upsert_search_index", mock_upsert)
    result = await writer.persist_search_vectors(fake_session_factory, vectors(), indexed_hash="v1:" + "a" * 64)
    assert result is IndexStatus.INDEXED
    mock_upsert.assert_awaited_once()
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_writer_unchanged_index(monkeypatch):
    upsert = AsyncMock()
    monkeypatch.setattr(writer, "get_index_lexemes", AsyncMock(return_value=("python",)))
    monkeypatch.setattr(writer, "synchronize_vocabulary", AsyncMock())
    monkeypatch.setattr(writer, "get_document_for_update", AsyncMock(return_value=source()))
    monkeypatch.setattr(writer, "get_search_index", AsyncMock(return_value=stored()))
    monkeypatch.setattr(writer, "upsert_search_index", upsert)
    result = await writer.persist_search_vectors(fake_session_factory, vectors(), indexed_hash="v1:" + "a" * 64)
    assert result is IndexStatus.UNCHANGED
    upsert.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_source", [None, source(is_available=False), source(source_id=11), source(updated_at=NOW + timedelta(seconds=1))])
async def test_writer_rejects_stale(monkeypatch, bad_source):
    upsert = AsyncMock()
    monkeypatch.setattr(writer, "lock_vocabulary", AsyncMock())
    monkeypatch.setattr(writer, "get_index_lexemes", AsyncMock(return_value=()))
    monkeypatch.setattr(writer, "synchronize_vocabulary", AsyncMock())
    monkeypatch.setattr(writer, "get_document_for_update", AsyncMock(return_value=bad_source))
    monkeypatch.setattr(writer, "get_search_index", AsyncMock())
    monkeypatch.setattr(writer, "upsert_search_index", upsert)
    assert await writer.persist_search_vectors(fake_session_factory, vectors(), indexed_hash="v1:" + "a" * 64) is IndexStatus.STALE
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_writer_rebuilds_outdated_timestamp(monkeypatch):
    upsert = AsyncMock()
    monkeypatch.setattr(writer, "get_document_for_update", AsyncMock(return_value=source()))
    monkeypatch.setattr(writer, "get_search_index", AsyncMock(return_value=stored(indexed_at=NOW - timedelta(seconds=1))))
    monkeypatch.setattr(writer, "upsert_search_index", upsert)
    assert await writer.persist_search_vectors(fake_session_factory, vectors(), indexed_hash="v1:" + "a" * 64) is IndexStatus.INDEXED
    upsert.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("existing,removed,expected", [
    (None, True, IndexStatus.REMOVED),
    (source(is_available=False), True, IndexStatus.REMOVED),
    (None, False, IndexStatus.SKIPPED),
    (source(), False, IndexStatus.STALE),
])
async def test_removal_guards_active_sources(monkeypatch, existing, removed, expected):
    delete = AsyncMock(return_value=removed)
    monkeypatch.setattr(writer, "get_index_lexemes", AsyncMock(return_value=("python",)))
    monkeypatch.setattr(writer, "synchronize_vocabulary", AsyncMock())
    monkeypatch.setattr(writer, "remove_indexed_documents", AsyncMock(return_value=int(removed)))
    monkeypatch.setattr(writer, "get_document_for_update", AsyncMock(return_value=existing))
    monkeypatch.setattr(writer, "delete_search_index", delete)
    assert await writer.remove_search_index(fake_session_factory, 1) is expected
    if expected is IndexStatus.STALE:
        delete.assert_not_awaited()
        writer.remove_indexed_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_full_index(monkeypatch):
    cfg = IndexerConfig()
    candidate = IndexCandidate(document_id=1, source_updated_at=NOW)
    doc = SimpleNamespace(document_id=1)
    analyzed = object()
    vec = vectors()
    load = AsyncMock(return_value=doc)
    persist = AsyncMock(return_value=IndexStatus.INDEXED)
    monkeypatch.setattr(service, "build_index_document", load)
    monkeypatch.setattr(service, "calculate_index_hash", lambda *a, **k: "v1:" + "a" * 64)
    monkeypatch.setattr(service, "analyze_index_document", lambda *a, **k: analyzed)
    monkeypatch.setattr(service, "build_search_vectors", lambda *a, **k: vec)
    monkeypatch.setattr(service, "persist_search_vectors", persist)
    result = await service.index_candidate(fake_session_factory, candidate, config=cfg)
    assert result.status is IndexStatus.INDEXED
    assert result.indexed_hash == "v1:" + "a" * 64
    assert result.duration_ms >= 0
    load.assert_awaited_once()
    persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_marks_stale(monkeypatch):
    from indexer.errors import StaleIndexSourceError
    candidate = IndexCandidate(document_id=1, source_updated_at=NOW)
    monkeypatch.setattr(service, "build_index_document", AsyncMock(side_effect=StaleIndexSourceError("changed")))
    persist = AsyncMock()
    monkeypatch.setattr(service, "persist_search_vectors", persist)
    result = await service.index_candidate(fake_session_factory, candidate, config=IndexerConfig())
    assert result.status is IndexStatus.STALE
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_does_not_swallow_database_errors(monkeypatch):
    candidate = IndexCandidate(document_id=1, source_updated_at=NOW)
    monkeypatch.setattr(service, "build_index_document", AsyncMock(side_effect=RuntimeError("db is down")))
    with pytest.raises(RuntimeError, match="db is down"):
        await service.index_candidate(fake_session_factory, candidate, config=IndexerConfig())


@pytest.mark.asyncio
async def test_service_remove_result(monkeypatch):
    monkeypatch.setattr(service, "remove_search_index", AsyncMock(return_value=IndexStatus.REMOVED))
    result = await service.remove_candidate(fake_session_factory, 1)
    assert result.document_id == 1
    assert result.status is IndexStatus.REMOVED
