"""Unit tests for selection policy and repository delegation.

No PostgreSQL connection is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from retrieval_vocabulary import selector
from retrieval_vocabulary.errors import VocabularyValidationError
from retrieval_vocabulary.schema import VocabularyAction, VocabularyCandidate


HASH_A = "v1:" + "a" * 64
HASH_B = "v2:" + "b" * 64


@pytest.mark.asyncio
async def test_sync_converts_repository_rows_to_candidates(monkeypatch):
    fetch = AsyncMock(return_value=[(101, HASH_A), (104, HASH_B)])
    monkeypatch.setattr(selector, "fetch_pending_sync_rows", fetch)
    session = object()

    result = await selector.select_sync_candidates(
        session, limit=2, after_document_id=100
    )

    assert result == [
        VocabularyCandidate(
            document_id=101, action=VocabularyAction.SYNC, indexed_hash=HASH_A
        ),
        VocabularyCandidate(
            document_id=104, action=VocabularyAction.SYNC, indexed_hash=HASH_B
        ),
    ]
    fetch.assert_awaited_once_with(
        session, limit=2, after_document_id=100
    )


@pytest.mark.asyncio
async def test_sync_returns_empty_list_when_no_work(monkeypatch):
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(selector, "fetch_pending_sync_rows", fetch)

    result = await selector.select_sync_candidates(object())

    assert result == []
    assert fetch.await_args.kwargs == {"limit": 100, "after_document_id": 0}


@pytest.mark.asyncio
async def test_removal_returns_remove_candidates(monkeypatch):
    fetch = AsyncMock(return_value=[22, 25])
    monkeypatch.setattr(selector, "fetch_pending_removal_ids", fetch)
    session = object()

    result = await selector.select_removal_candidates(
        session, limit=5, after_document_id=20
    )

    assert result == [
        VocabularyCandidate(
            document_id=22, action=VocabularyAction.REMOVE, indexed_hash=None
        ),
        VocabularyCandidate(
            document_id=25, action=VocabularyAction.REMOVE, indexed_hash=None
        ),
    ]
    fetch.assert_awaited_once_with(
        session, limit=5, after_document_id=20
    )


@pytest.mark.asyncio
async def test_removal_returns_empty_list_when_no_work(monkeypatch):
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(selector, "fetch_pending_removal_ids", fetch)

    assert await selector.select_removal_candidates(object()) == []
    assert fetch.await_args.kwargs == {"limit": 100, "after_document_id": 0}


@pytest.mark.parametrize("limit", [0, -1, 10_001, True, 1.0, "100", None])
@pytest.mark.parametrize(
    "method_name", ["select_sync_candidates", "select_removal_candidates"]
)
@pytest.mark.asyncio
async def test_rejects_invalid_limit(method_name, limit):
    method = getattr(selector, method_name)
    with pytest.raises(VocabularyValidationError, match="limit"):
        await method(object(), limit=limit)


@pytest.mark.parametrize("cursor", [-1, True, 1.5, "10", None])
@pytest.mark.parametrize(
    "method_name", ["select_sync_candidates", "select_removal_candidates"]
)
@pytest.mark.asyncio
async def test_rejects_invalid_cursor(method_name, cursor):
    method = getattr(selector, method_name)
    with pytest.raises(VocabularyValidationError, match="after_document_id"):
        await method(object(), after_document_id=cursor)


@pytest.mark.parametrize(
    "method_name,repository_name",
    [
        ("select_sync_candidates", "fetch_pending_sync_rows"),
        ("select_removal_candidates", "fetch_pending_removal_ids"),
    ],
)
@pytest.mark.asyncio
async def test_validation_happens_before_query(
    monkeypatch, method_name, repository_name
):
    fetch = AsyncMock()
    monkeypatch.setattr(selector, repository_name, fetch)
    method = getattr(selector, method_name)

    with pytest.raises(VocabularyValidationError):
        await method(object(), limit=0)

    fetch.assert_not_awaited()
