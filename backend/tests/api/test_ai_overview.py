"""Backend HTTP boundaries with the provider/store stubbed, never a real Groq call."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.ai_overview import context, service
from backend.ai_overview.store import Outcome
from backend.core.config import settings
from backend.main import app
from backend.schema.search import SearchResultOut

client = TestClient(app)


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("fake-key"))
    monkeypatch.setattr(settings, "ai_overview", True)
    result = SearchResultOut(title="Docs", url="https://example.com/docs", snippet="Useful evidence.",
                             source="docs", score=1, type="documentation")
    return context.sign_context("python", [result])


def test_backend_endpoint_owns_validation_and_retry_after(token, monkeypatch):
    generate = AsyncMock(return_value=Outcome(status=429, retry_after=120, error="Limited"))
    monkeypatch.setattr(service, "overview", generate)
    response = client.post("/search/overview", json={"token": token})
    assert response.status_code == 429 and response.headers["retry-after"] == "120"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"overview": None, "error": "Limited"}
    assert generate.call_args.args[0].query == "python"
    assert len(generate.call_args.args[1]) == 64, "only a client hash reaches state storage"


@pytest.mark.parametrize("body,status", [({}, 400), ({"token": "tampered"}, 400),
    ({"token": "x" * 25001}, 413), ({"query": "invented", "results": []}, 400)])
def test_invalid_evidence_never_generates(token, monkeypatch, body, status):
    generate = AsyncMock()
    monkeypatch.setattr(service, "overview", generate)
    assert client.post("/search/overview", json=body).status_code == status
    generate.assert_not_called()


def test_disabled_and_non_json(token, monkeypatch):
    assert client.post("/search/overview", json={"token": token}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/search/overview", content="hello").status_code == 415
    monkeypatch.setattr(settings, "ai_overview", False)
    assert client.post("/search/overview", json={}).json() == {"overview": None}


def test_untrusted_client_headers_cannot_change_identity(token, monkeypatch):
    monkeypatch.setattr(settings, "ai_overview_client_ip_header", "")
    generate = AsyncMock(return_value=Outcome())
    monkeypatch.setattr(service, "overview", generate)
    for ip in ["1.1.1.1", "2.2.2.2"]:
        assert client.post("/search/overview", json={"token": token}, headers={"X-Eye-Client-IP": ip, "X-Forwarded-For": ip}).status_code == 200
    assert generate.call_args_list[0].args[1] == generate.call_args_list[1].args[1]


def test_search_issues_backend_evidence(monkeypatch, token):
    from contextlib import asynccontextmanager
    import backend.api.search as api
    @asynccontextmanager
    async def session():
        yield object()
    result = SearchResultOut(title="Docs", url="https://example.com/docs", snippet="Useful evidence.", source="docs", score=1, type="documentation")
    monkeypatch.setattr(api, "SessionFactory", session)
    monkeypatch.setattr(api, "apply_query_deadline", AsyncMock())
    search = AsyncMock(return_value=[result])
    monkeypatch.setattr(api, "search_documents", search)
    response = client.get("/search", params={"q": "python"})
    assert response.status_code == 200
    snapshot = context.verify_context(response.json()["overview_token"])
    assert snapshot.query == "python" and snapshot.sources[0].url == result.url
    search.assert_awaited_once()
