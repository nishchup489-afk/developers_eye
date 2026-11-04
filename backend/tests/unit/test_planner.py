"""Unit tests for search mode parsing and retrieval target selection (no database)."""

from __future__ import annotations

import dataclasses

import pytest

from backend.search.query_selector.planner import (
    RetrievalTarget,
    SearchMode,
    SearchPlan,
    select_query_plan,
)


@pytest.mark.parametrize(
    ("mode", "targets"),
    [
        (SearchMode.ALL, (RetrievalTarget.TEXT, RetrievalTarget.CODE)),
        (SearchMode.TEXT, (RetrievalTarget.TEXT,)),
        (SearchMode.CODE, (RetrievalTarget.CODE,)),
    ],
)
def test_mode_selects_targets(mode, targets):
    """Each mode picks its retrieval channels; ALL searches text first, then code."""
    plan = select_query_plan("python async", mode=mode)
    assert plan == SearchPlan(query="python async", mode=mode, targets=targets)


def test_default_mode_is_all():
    """No mode and no default searches both channels."""
    plan = select_query_plan("fastapi")
    assert plan.mode is SearchMode.ALL
    assert plan.targets == (RetrievalTarget.TEXT, RetrievalTarget.CODE)


def test_default_mode_is_used_when_mode_is_none():
    """default_mode applies only when the caller gave no mode."""
    assert select_query_plan("x", default_mode="code").mode is SearchMode.CODE
    assert select_query_plan("x", mode="text", default_mode="code").mode is SearchMode.TEXT


@pytest.mark.parametrize("raw", ["text", "TEXT", " Text ", "\tcode\n", "ALL"])
def test_mode_strings_are_trimmed_and_case_insensitive(raw):
    """Mode strings from query parameters are normalized before parsing."""
    assert select_query_plan("x", mode=raw).mode is SearchMode(raw.strip().lower())


def test_query_is_trimmed():
    """Outer whitespace is removed; inner spacing is left to the analyzer."""
    assert select_query_plan("  python   async \n").query == "python   async"


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query_is_rejected(query):
    with pytest.raises(ValueError, match="empty"):
        select_query_plan(query)


@pytest.mark.parametrize("query", [None, 42, b"python", ["python"]])
def test_non_string_query_is_rejected(query):
    with pytest.raises(TypeError, match="Query must be a string"):
        select_query_plan(query)


@pytest.mark.parametrize("mode", ["", "fuzzy", "texts", "all code"])
def test_unknown_mode_is_rejected(mode):
    with pytest.raises(ValueError, match="Unsupported search mode"):
        select_query_plan("x", mode=mode)


@pytest.mark.parametrize("mode", [1, 0.5, ["text"], RetrievalTarget.TEXT.value.encode()])
def test_non_string_mode_is_rejected(mode):
    with pytest.raises(TypeError, match="Search mode"):
        select_query_plan("x", mode=mode)


def test_invalid_default_mode_is_rejected_when_used():
    with pytest.raises(ValueError, match="Unsupported search mode"):
        select_query_plan("x", default_mode="nope")


def test_plan_is_immutable():
    """SearchPlan is frozen, so a plan cannot be changed after selection."""
    plan = select_query_plan("x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.mode = SearchMode.CODE  # type: ignore[misc]
