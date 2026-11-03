"""Suggestion behavior without requiring a live PostgreSQL connection."""

from unittest.mock import AsyncMock

import pytest

import backend.search.retrieval.fuzzy.correction as correction
from backend.schema.search_term import FuzzyCandidate


@pytest.mark.asyncio
async def test_corrects_spelling_using_vocabulary(monkeypatch):
    monkeypatch.setattr(correction, "get_exact_term", AsyncMock(return_value=None))
    candidates = AsyncMock(return_value=[FuzzyCandidate(
        term="python", similarity=0.9, document_frequency=50
    )])
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates)
    result = await correction.suggest_query_correction("pythonn", AsyncMock())
    assert result.suggested_query == "python"
    assert result.changed
    assert result.corrections[0].edit_distance == 1
    candidates.assert_awaited_once()


@pytest.mark.asyncio
async def test_does_not_modify_exact_terms(monkeypatch):
    exact = AsyncMock(return_value=object())
    candidates = AsyncMock()
    monkeypatch.setattr(correction, "get_exact_term", exact)
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates)
    result = await correction.suggest_query_correction("python", AsyncMock())
    assert not result.changed
    candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_does_not_correct_technical_identifier(monkeypatch):
    candidates = AsyncMock()
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates)
    result = await correction.suggest_query_correction("AsyncSession fastapi.utils", AsyncMock())
    assert not result.changed
    candidates.assert_not_awaited()
