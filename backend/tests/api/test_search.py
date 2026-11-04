"""HTTP tests for GET /search parameters and GET /search/suggest.

test_search_route.py covers the basic contract (shape, 422 on bad input, 503 on a
database error). This file covers how page, mode and limit reach the search
service, the remaining error mappings, and the suggestion endpoint. The
database is never touched: the session factory and services are stubbed.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import backend.api.search as search_api
from backend.main import app
from backend.schema.search_term import QueryCorrection, TermCorrection
from backend.search.query_analyzer.analyzer import QueryErrorCode, QueryValidationError
from backend.search.query_selector.planner import SearchMode

client = TestClient(app)


@asynccontextmanager
async def fake_session():
    yield object()


@pytest.fixture
def calls(monkeypatch):
    """Record the keyword arguments each search_documents call receives."""
    seen: list[dict] = []

    async def fake_search(session, query, **kwargs):
        seen.append({"query": query, **kwargs})
        return []

    monkeypatch.setattr(search_api, "SessionFactory", fake_session)
    monkeypatch.setattr(search_api, "search_documents", fake_search)
    return seen


def test_default_request_keeps_old_call_signature(calls):
    """Page 1 and mode=all are not passed, so older service signatures still work."""
    assert client.get("/search", params={"q": "python"}).status_code == 200
    assert calls == [{"query": "python", "category": None, "limit": 20}]


def test_page_and_mode_are_forwarded(calls):
    response = client.get("/search", params={"q": "python", "page": 3, "mode": "code", "limit": 50})
    assert response.status_code == 200
    assert response.json() == {"query": "python", "results": []}
    assert calls == [{"query": "python", "category": None, "limit": 50, "page": 3,
                      "mode": SearchMode.CODE}]


@pytest.mark.parametrize(
    "params",
    [{"q": "a", "limit": 51}, {"q": "a", "page": 0}, {"q": "a", "page": -1},
     {"q": "a", "mode": "fuzzy"}, {"q": "a", "limit": "ten"}, {"q": "x" * 1025}],
)
def test_out_of_range_parameters_are_422(calls, params):
    assert client.get("/search", params=params).status_code == 422
    assert calls == []


@pytest.mark.parametrize(
    "error",
    [ValueError("offset cannot exceed 1000"),
     QueryValidationError(QueryErrorCode.EMPTY, "Query cannot be empty")],
)
def test_service_validation_errors_are_422(monkeypatch, calls, error):
    async def reject(*args, **kwargs):
        raise error

    monkeypatch.setattr(search_api, "search_documents", reject)
    assert client.get("/search", params={"q": "python", "page": 999}).status_code == 422


def test_uninitialized_engine_is_503(monkeypatch, calls):
    """RuntimeError (e.g. BM25 corpus statistics not loaded) maps to 503, without details."""
    async def not_ready(*args, **kwargs):
        raise RuntimeError("BM25 corpus statistics not initialized; secret detail")

    monkeypatch.setattr(search_api, "search_documents", not_ready)
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Search engine is not initialized"}


# ---------------------------------------------------------------- /search/suggest

@pytest.fixture
def suggest(monkeypatch):
    seen: list[str] = []

    async def fake_suggest(query, session):
        seen.append(query)
        return QueryCorrection(
            original_query=query,
            suggested_query="python async",
            corrections=[TermCorrection(original="pyhton", replacement="python",
                                        similarity=0.8, edit_distance=2)],
        )

    monkeypatch.setattr(search_api, "SessionFactory", fake_session)
    monkeypatch.setattr(search_api, "suggest_query_correction", fake_suggest)
    return seen


def test_suggest_returns_correction_for_normalized_query(suggest):
    response = client.get("/search/suggest", params={"q": "  pyhton   async "})
    assert response.status_code == 200
    assert suggest == ["pyhton async"]
    body = response.json()
    assert body["original_query"] == "pyhton async"
    assert body["suggested_query"] == "python async"
    assert body["corrections"][0]["replacement"] == "python"


@pytest.mark.parametrize("params", [{}, {"q": "   "}, {"q": "a\x00b"}])
def test_suggest_rejects_invalid_query(suggest, params):
    assert client.get("/search/suggest", params=params).status_code == 422
    assert suggest == []


def test_suggest_database_error_is_503(monkeypatch, suggest):
    async def broken(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("vocabulary down"))

    monkeypatch.setattr(search_api, "suggest_query_correction", broken)
    response = client.get("/search/suggest", params={"q": "python"})
    assert response.status_code == 503
    assert "vocabulary down" not in response.text
