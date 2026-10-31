"""Unit tests for retrieval_vocabulary.builder (no database required)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from retrieval_vocabulary import builder
from retrieval_vocabulary.errors import (
    VocabularyBuildError,
    VocabularyValidationError,
)
from retrieval_vocabulary.schema import (
    VocabularyAction,
    VocabularyCandidate,
    VocabularyDocument,
)


HASH = "v1:" + "a" * 64


def candidate(*, action: VocabularyAction = VocabularyAction.SYNC):
    return VocabularyCandidate(
        document_id=101,
        action=action,
        indexed_hash=HASH if action == VocabularyAction.SYNC else None,
    )


def source(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "document_id": 101,
        "indexed_hash": HASH,
        "title": "Python Async Programming",
        "description": "Async programming guide",
        "body": "Python supports asyncio.",
        "headings": ["Introduction", "Functions"],
        "code_blocks": ["async def main(): pass"],
        "tags": ["python", "asyncio"],
    }
    record.update(overrides)
    return record


@pytest.mark.asyncio
async def test_builds_validated_document_from_repository(monkeypatch):
    fetch = AsyncMock(return_value=source())
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)
    session = object()

    result = await builder.build_vocabulary_document(candidate(), session)

    assert isinstance(result, VocabularyDocument)
    assert result.document_id == 101
    assert result.indexed_hash == HASH
    assert result.title == "Python Async Programming"
    assert result.description == "Async programming guide"
    assert result.body == "Python supports asyncio."
    assert result.headings == ("Introduction", "Functions")
    assert result.code_blocks == ("async def main(): pass",)
    assert result.tags == ("python", "asyncio")
    fetch.assert_awaited_once_with(
        session, document_id=101, indexed_hash=HASH
    )


@pytest.mark.asyncio
async def test_returns_none_when_repository_reports_missing_or_stale(monkeypatch):
    fetch = AsyncMock(return_value=None)
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    result = await builder.build_vocabulary_document(candidate(), object())

    assert result is None
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_nullable_fields_become_empty_values(monkeypatch):
    fetch = AsyncMock(
        return_value=source(
            title=None,
            description=None,
            body=None,
            headings=None,
            code_blocks=None,
            tags=None,
        )
    )
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    result = await builder.build_vocabulary_document(candidate(), object())

    assert result is not None
    assert (result.title, result.description, result.body) == ("", "", "")
    assert (result.headings, result.code_blocks, result.tags) == ((), (), ())


@pytest.mark.asyncio
async def test_tuple_fields_are_preserved(monkeypatch):
    fetch = AsyncMock(
        return_value=source(
            headings=("A", "B"),
            code_blocks=("print(1)",),
            tags=("python",),
        )
    )
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    result = await builder.build_vocabulary_document(candidate(), object())

    assert result is not None
    assert result.headings == ("A", "B")
    assert result.code_blocks == ("print(1)",)
    assert result.tags == ("python",)


@pytest.mark.parametrize("field", ["title", "description", "body"])
@pytest.mark.asyncio
async def test_rejects_invalid_text_fields(monkeypatch, field):
    fetch = AsyncMock(return_value=source(**{field: 123}))
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    with pytest.raises(VocabularyBuildError, match=field):
        await builder.build_vocabulary_document(candidate(), object())


@pytest.mark.parametrize("field", ["headings", "code_blocks", "tags"])
@pytest.mark.parametrize("bad_value", ["single string", ["valid", 42], {"x": 1}])
@pytest.mark.asyncio
async def test_rejects_invalid_list_fields(monkeypatch, field, bad_value):
    fetch = AsyncMock(return_value=source(**{field: bad_value}))
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    with pytest.raises(VocabularyBuildError, match=field):
        await builder.build_vocabulary_document(candidate(), object())


@pytest.mark.parametrize(
    "bad_fields",
    [
        {"document_id": -1},
        {"indexed_hash": ""},
    ],
)
@pytest.mark.asyncio
async def test_wraps_pydantic_validation_failures(monkeypatch, bad_fields):
    fetch = AsyncMock(return_value=source(**bad_fields))
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    with pytest.raises(VocabularyBuildError, match="Invalid vocabulary document"):
        await builder.build_vocabulary_document(candidate(), object())


@pytest.mark.asyncio
async def test_rejects_non_candidate_before_read(monkeypatch):
    fetch = AsyncMock()
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    with pytest.raises(TypeError, match="VocabularyCandidate"):
        await builder.build_vocabulary_document(101, object())

    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_remove_candidate_before_read(monkeypatch):
    fetch = AsyncMock()
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    with pytest.raises(VocabularyValidationError, match="SYNC"):
        await builder.build_vocabulary_document(
            candidate(action=VocabularyAction.REMOVE), object()
        )

    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_does_not_swallow_repository_errors(monkeypatch):
    fetch = AsyncMock(side_effect=RuntimeError("database offline"))
    monkeypatch.setattr(builder, "fetch_indexed_document", fetch)

    with pytest.raises(RuntimeError, match="database offline"):
        await builder.build_vocabulary_document(candidate(), object())
