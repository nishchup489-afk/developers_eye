"""Vocabulary filtering and count-delta unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from indexer.vocabulary import synchronize_vocabulary, vocabulary_terms


def test_vocabulary_filters_artifacts_and_keeps_developer_terms():
    actual = vocabulary_terms([
        "Python", "PYTHON", "fastapi", "asyncio", "C++", "c#",
        "a00000000006e1_u64", "python-3.13-docs-html.zip", "' ||",
        "a1b2c3d4", "run", "applic",
    ])
    assert {"python", "fastapi", "asyncio", "c++", "c#", "run", "applic"} <= actual
    assert "python-3.13-docs-html.zip" not in actual
    assert "' ||" not in actual


def test_vocabulary_rejects_non_string_lexemes():
    with pytest.raises(TypeError):
        vocabulary_terms(["python", None])


@pytest.mark.asyncio
async def test_unchanged_document_does_not_write_counts():
    session = AsyncMock()
    await synchronize_vocabulary(
        session, old_lexemes=["python", "fastapi", "python"],
        new_lexemes=["fastapi", "python"],
    )
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_addition_issues_conflict_safe_upsert():
    session = AsyncMock()
    await synchronize_vocabulary(
        session, old_lexemes=[], new_lexemes=["python", "python"],
    )
    assert session.execute.await_count == 1
    assert "ON CONFLICT" in str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_removal_decrements_and_deletes_zero_count():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = 0
    session.execute.return_value = result
    await synchronize_vocabulary(
        session, old_lexemes=["django"], new_lexemes=[],
    )
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_missing_frequency_raises_and_caller_rolls_back():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    with pytest.raises(RuntimeError, match="drift"):
        await synchronize_vocabulary(
            session, old_lexemes=["django"], new_lexemes=[],
        )
