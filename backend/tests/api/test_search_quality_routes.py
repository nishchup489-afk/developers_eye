"""HTTP contract for the admin search-quality routes and slow-search recording (ADR-0057)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import backend.api.search as search_api
import backend.api.search_quality as quality_api
from backend.admin_services import search_quality as quality
from backend.core.config import settings
from backend.main import app
from backend.search.trace import stage

client = TestClient(app)
KEY = "k" * 40
AUTH = {"Authorization": f"Bearer {KEY}"}


@pytest.fixture(autouse=True)
def report_key(monkeypatch):
    monkeypatch.setattr(settings, "crawler_report_api_key", SecretStr(KEY))


class FakeSession:
    @asynccontextmanager
    async def begin(self):
        yield


@asynccontextmanager
async def fake_factory():
    yield FakeSession()


def test_routes_need_the_report_key():
    assert client.get("/admin/search-quality/slow").status_code == 401
    assert client.put("/admin/search-quality/queries/H001", json={"query": "x"}).status_code == 401
    assert client.get("/admin/search-quality/evaluation", params={"k": 7}, headers=AUTH).status_code == 422


def test_write_errors_map_to_422_and_missing_queries_to_404(monkeypatch):
    monkeypatch.setattr(quality_api, "SessionFactory", fake_factory)

    async def invalid(session, query_id, payload, *, judge):
        raise quality.JudgingError("grade must be 0, 1, 2, 3 or null")

    async def missing(session, query_id, payload, *, judge):
        return None

    monkeypatch.setattr(quality, "save_judgment", invalid)
    response = client.put("/admin/search-quality/queries/H001/judgments", json={"url": "https://a.dev", "grade": 9}, headers=AUTH)
    assert response.status_code == 422 and "grade" in response.json()["detail"]
    monkeypatch.setattr(quality, "save_judgment", missing)
    assert client.put("/admin/search-quality/queries/NOPE/judgments", json={"url": "https://a.dev"}, headers=AUTH).status_code == 404


def test_judge_name_is_passed_through_and_truncated(monkeypatch):
    monkeypatch.setattr(quality_api, "SessionFactory", fake_factory)
    seen = {}

    async def save(session, query_id, payload, *, judge):
        seen.update(query_id=query_id, judge=judge)
        return {"ok": True}

    monkeypatch.setattr(quality, "save_judgment", save)
    response = client.put("/admin/search-quality/queries/H001/judgments",
                          json={"url": "https://a.dev", "grade": 2, "judge": "n" * 100}, headers=AUTH)
    assert response.status_code == 200
    assert seen == {"query_id": "H001", "judge": "n" * 64}


@asynccontextmanager
async def search_session():
    yield object()


def test_timed_out_search_is_kept_with_the_stage_it_stopped_in(monkeypatch):
    async def no_deadline(session):
        return None

    async def slow_search(session, query, **kwargs):
        with stage("retrieval"):
            pass
        with stage("ranking"):
            await asyncio.sleep(5)

    kept = []
    monkeypatch.setattr(search_api, "apply_query_deadline", no_deadline)
    monkeypatch.setattr(search_api, "SessionFactory", search_session)
    monkeypatch.setattr(search_api, "search_documents", slow_search)
    monkeypatch.setattr(search_api, "TOTAL_DEADLINE_SECONDS", 0.05)
    monkeypatch.setattr(search_api.telemetry, "record_slow", lambda **row: kept.append(row))

    assert client.get("/search", params={"q": "HTTP 500 internal server error"}).status_code == 504
    assert len(kept) == 1
    row = kept[0]
    assert (row["query"], row["outcome"], row["stopped_in"]) == ("HTTP 500 internal server error", "timed_out", "ranking")
    assert "retrieval" in row["stages"] and row["result_count"] is None
