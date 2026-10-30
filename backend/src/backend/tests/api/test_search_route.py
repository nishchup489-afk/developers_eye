"""HTTP contract tests for GET /search, with the database call stubbed out."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import backend.api.search as search_api
from backend.main import app
from backend.schema.search import SearchResultOut

client = TestClient(app)


@pytest.fixture
def stub(monkeypatch):
    calls = []

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def fake_search(session, query, *, category=None, limit=20):
        calls.append((query, category, limit))
        return [SearchResultOut(title="T", source="docs", url="https://a.dev/x",
                                snippet="s", score=0.5, tags=["python"], type="documentation")]

    monkeypatch.setattr(search_api, "SessionFactory", fake_session)
    monkeypatch.setattr(search_api, "search_documents", fake_search)
    return calls


def test_returns_results(stub):
    response = client.get("/search", params={"q": "  fastapi   async ", "source": "docs"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "query": "fastapi async",
        "results": [{"title": "T", "source": "docs", "url": "https://a.dev/x", "snippet": "s",
                     "score": 0.5, "tags": ["python"], "type": "documentation"}],
    }
    assert stub == [("fastapi async", "docs", 20)]


@pytest.mark.parametrize(
    "params",
    [{}, {"q": "   "}, {"q": "x" * 301}, {"q": "a\x00b"}, {"q": "a", "source": "nope"},
     {"q": "a", "limit": 0}],
)
def test_rejects_invalid_input(stub, params):
    assert client.get("/search", params=params).status_code == 422
    assert stub == []


def test_database_error_is_503(monkeypatch, stub):
    async def broken(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("down"))

    monkeypatch.setattr(search_api, "search_documents", broken)
    response = client.get("/search", params={"q": "async"})
    assert response.status_code == 503
    assert "down" not in response.text
