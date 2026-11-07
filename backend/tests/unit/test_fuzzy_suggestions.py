"""Suggestion behavior without requiring a live PostgreSQL connection."""

from unittest.mock import AsyncMock

import pytest

import backend.search.retrieval.fuzzy.correction as correction
from backend.schema.search_term import FuzzyCandidate


def fake_stemmer(stems: dict[str, str] | None = None) -> AsyncMock:
    """english_stems stand-in: listed words map to a stem, others to themselves."""
    table = stems or {}

    async def stem(words, session):
        return {word: table.get(word, word) for word in words}

    return AsyncMock(side_effect=stem)


def exact_terms(*terms: str) -> AsyncMock:
    known = set(terms)

    async def exact(term, session):
        return object() if term in known else None

    return AsyncMock(side_effect=exact)


def candidates_of(*terms: str) -> AsyncMock:
    return AsyncMock(return_value=[
        FuzzyCandidate(term=term, similarity=0.6, document_frequency=50) for term in terms
    ])


@pytest.fixture(autouse=True)
def identity_stems(monkeypatch):
    monkeypatch.setattr(correction, "english_stems", fake_stemmer())


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


@pytest.mark.asyncio
async def test_stem_candidate_is_shown_as_a_real_word(monkeypatch):
    monkeypatch.setattr(correction, "get_exact_term", exact_terms("configur"))
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates_of("configur"))
    monkeypatch.setattr(correction, "english_stems", fake_stemmer({
        "configure": "configur", "configured": "configur", "configuration": "configur",
        "configurations": "configur",
    }))
    result = await correction.suggest_query_correction("fastapi configuraton", AsyncMock())
    assert result.suggested_query == "fastapi configuration"
    assert result.corrections[0].replacement == "configuration"
    assert result.corrections[0].edit_distance == 1


@pytest.mark.asyncio
async def test_y_stem_is_shown_as_a_real_word(monkeypatch):
    monkeypatch.setattr(correction, "get_exact_term", exact_terms("librari"))
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates_of("librari"))
    monkeypatch.setattr(correction, "english_stems", fake_stemmer({
        "library": "librari", "libraries": "librari",
    }))
    result = await correction.suggest_query_correction("libary", AsyncMock())
    assert result.suggested_query == "library"


@pytest.mark.asyncio
async def test_unverified_forms_never_surface_a_bare_stem(monkeypatch):
    # The stemmer confirms no surface word, and the bare stem is too far away.
    monkeypatch.setattr(correction, "get_exact_term", exact_terms("configur"))
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates_of("configur"))
    result = await correction.suggest_query_correction("configuraton", AsyncMock())
    assert not result.changed
    assert result.corrections == []


@pytest.mark.asyncio
async def test_bare_stem_ending_in_i_is_skipped(monkeypatch):
    monkeypatch.setattr(correction, "get_exact_term", exact_terms("queri"))
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates_of("queri"))
    # "querie" is one edit from "queri"; no real form reduces back to it.
    result = await correction.suggest_query_correction("querie", AsyncMock())
    assert not result.changed


@pytest.mark.asyncio
async def test_word_whose_stem_is_indexed_is_not_a_typo(monkeypatch):
    candidates = AsyncMock()
    monkeypatch.setattr(correction, "get_exact_term", exact_terms("configur"))
    monkeypatch.setattr(correction, "find_fuzzy_candidates", candidates)
    monkeypatch.setattr(correction, "english_stems", fake_stemmer({"configuration": "configur"}))
    result = await correction.suggest_query_correction("configuration", AsyncMock())
    assert not result.changed
    candidates.assert_not_awaited()


def test_surface_forms_start_with_the_stem_and_rebuild_y_words():
    forms = correction.surface_forms("librari")
    assert forms[0] == "librari"
    assert {"library", "libraries"} <= set(forms)
    assert "configuration" in correction.surface_forms("configur")
    assert len(forms) == len(set(forms))
