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
async def test_unchanged_document_queues_nothing():
    session = MagicMock(flush=AsyncMock())
    await synchronize_vocabulary(
        session, old_lexemes=["python", "fastapi", "python"],
        new_lexemes=["fastapi", "python"],
    )
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_change_queues_sorted_added_and_removed_terms():
    session = MagicMock(flush=AsyncMock())
    await synchronize_vocabulary(
        session, old_lexemes=["django", "python", "flask"], new_lexemes=["rust", "python", "async"],
    )
    change = session.add.call_args.args[0]
    assert change.added == ["async", "rust"]
    assert change.removed == ["django", "flask"]
