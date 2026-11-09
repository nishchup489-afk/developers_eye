"""Grounding, evidence integrity and sliding quotas without network/database."""
import json
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from backend.ai_overview import context, provider, service
from backend.ai_overview.limits import reserve
from backend.ai_overview.prompt import SYSTEM_PROMPT, build_evidence, parse_answer
from backend.ai_overview.store import Claim, Outcome
from backend.core.config import settings
from backend.schema.search import SearchResultOut


@pytest.fixture
def evidence(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("fake-test-key"))
    monkeypatch.setattr(settings, "ai_overview", True)
    results = [SearchResultOut(title=f"Docs {index}", url=f"https://docs.example.com/{index}",
        snippet="Asyncio supports concurrent I/O using async/await.", source="docs", score=1, type="documentation") for index in range(5)]
    token = context.sign_context("python async", [results[0], *results])
    return context.verify_context(token), token, results


def test_signed_evidence(evidence, monkeypatch):
    snapshot, token, results = evidence
    assert len(snapshot.sources) == 4
    assert snapshot.query == "python async"
    assert context.verify_context(token + "tampered") is None
    assert context.verify_context("malformed") is None
    assert context.verify_context("payload.文") is None
    assert context.sign_context("empty", []) is None
    assert "fake-test-key" not in token
    monkeypatch.setattr(context.time, "time", lambda: snapshot.expires + 1)
    assert context.verify_context(token) is None
    monkeypatch.setattr(settings, "ai_overview", False)
    assert context.sign_context("python", results) is None


def test_context_skips_unsafe_or_oversized_urls(evidence):
    _, _, results = evidence
    results[0].url = "javascript:alert(1)"
    results[1].url = "https://example.com/" + "文" * 700
    snapshot = context.verify_context(context.sign_context("python", results))
    assert [source.url for source in snapshot.sources] == [result.url for result in results[2:]]


def test_prompt_and_output_validation(evidence):
    snapshot, *_ = evidence
    content, tokens = build_evidence(snapshot)
    assert tokens <= 5000
    assert "ONLY the provided" in SYSTEM_PROMPT and "untrusted data" in SYSTEM_PROMPT
    assert all("url" not in item for item in json.loads(content)["sources"])
    result = parse_answer('{"paragraphs":[{"text":" Answer ","sources":[2,2]}]}', snapshot)
    assert result.paragraphs[0].text == "Answer"
    assert [source.id for source in result.sources] == [2]
    assert parse_answer('{"paragraphs":[]}', snapshot) is None
    for paragraphs in [[{"text": "Answer", "sources": [99]}], [{"text": "Answer", "sources": []}],
                       [{"text": "Answer", "sources": [True]}], [{"text": " ", "sources": [1]}],
                       [{"text": "x" * 701, "sources": [1]}], [{"text": "x", "sources": [1]}] * 4]:
        with pytest.raises(ValueError):
            parse_answer(json.dumps({"paragraphs": paragraphs}), snapshot)


def test_multilingual_evidence_stays_bounded(evidence):
    snapshot, *_ = evidence
    for source in snapshot.sources:
        source.snippet = "中文的代码说明。" * 40
    content, tokens = build_evidence(snapshot)
    assert tokens <= 5000
    assert json.loads(content)["query"] == snapshot.query


def test_sliding_budgets_are_global_and_failed_reservations_are_not_added():
    state, retry = reserve({}, "a", 4000, 100000)
    assert retry == 0
    denied, retry = reserve(state, "b", 1001, 100001)
    assert retry == 59 and len(denied["day"]) == 1
    assert len(state["day"]) == 1, "pure reservation must not mutate input"
    state, retry = reserve(state, "b", 1000, 100001)
    assert retry == 0
    assert reserve(state, "a", 4000, 100060)[1] == 0
    state = {}
    for index in range(20):
        state, retry = reserve(state, str(index), 1, 100000)
        assert retry == 0
    assert reserve(state, "other", 1, 100000)[1] == 60


def test_client_daily_and_global_daily_limits():
    state = {}
    for minute in range(10):
        for second in range(3):
            state, retry = reserve(state, "client", 1, 100000 + minute * 60 + second)
            assert retry == 0
        assert reserve(state, "client", 1, 100000 + minute * 60 + 3)[1] > 0
    assert reserve(state, "client", 1, 100600)[1] > 80000
    assert reserve(state, "client", 1, 186400)[1] == 0
    state = {}
    for minute in range(32):
        state, retry = reserve(state, str(minute), 5000, 100000 + minute * 60)
        assert retry == 0
    assert reserve(state, "next", 1, 101920)[1] > 70000
    assert reserve({"blocked_until": 100120}, "anyone", 1, 100060)[1] == 60


@pytest.mark.parametrize("scenario,status", [("ok", 200), ("abstain", 200), ("bad-citation", 502),
    ("malformed", 502), ("truncated", 502), ("timeout", 504), ("limited", 429), ("unauthorized", 502)])
async def test_provider_contract(evidence, monkeypatch, scenario, status):
    snapshot, *_ = evidence
    content, _ = build_evidence(snapshot)
    def fake_request(received):
        assert received == content
        if scenario == "timeout":
            raise TimeoutError()
        if scenario == "limited":
            return 429, {"Retry-After": "120"}, b"private provider error"
        if scenario == "unauthorized":
            return 401, {}, b"secret diagnostic"
        output = {"paragraphs": [] if scenario == "abstain" else [{"text": "Answer", "sources": [99 if scenario == "bad-citation" else 1]}]}
        body = {"choices": [{"finish_reason": "length" if scenario == "truncated" else "stop",
                             "message": {"content": "{no" if scenario == "malformed" else json.dumps(output)}}]}
        return 200, {}, json.dumps(body).encode()
    monkeypatch.setattr(provider, "_request", fake_request)
    outcome = await provider.generate(snapshot, content)
    assert outcome.status == status
    assert "secret" not in str(outcome.body()) and "private" not in str(outcome.body())
    if scenario == "limited":
        assert outcome.retry_after == 120
    if scenario == "ok":
        assert outcome.overview["sources"][0]["url"] == snapshot.sources[0].url


async def test_service_cache_and_fail_closed(evidence, monkeypatch):
    snapshot, *_ = evidence
    store = AsyncMock()
    store.claim.return_value = Claim(outcome=Outcome())
    generate = AsyncMock()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(provider, "generate", generate)
    assert (await service.overview(snapshot, "client")).status == 200
    generate.assert_not_called()
    original_key = store.claim.call_args.args[0]
    refreshed = snapshot.model_copy(deep=True)
    refreshed.expires += 60
    await service.overview(refreshed, "client")
    assert store.claim.call_args.args[0] == original_key, "token refresh preserves the evidence cache key"
    refreshed.sources[0].snippet = "Different evidence"
    await service.overview(refreshed, "client")
    assert store.claim.call_args.args[0] != original_key
    store.claim.side_effect = ConnectionRefusedError("database down")
    assert (await service.overview(snapshot, "client")).status == 503
    generate.assert_not_called()


def test_transport_never_redirects_and_handles_retry_dates():
    assert provider.NoRedirect().redirect_request(None, None, 302, "", {}, "https://attacker.test") is None
    assert provider.retry_seconds("120") == 120
    assert provider.retry_seconds("nonsense") == 60
    assert provider.retry_seconds("inf") == 60


def test_transport_keeps_key_backend_only_and_bounds_response(evidence, monkeypatch):
    snapshot, *_ = evidence
    content, _ = build_evidence(snapshot)
    calls = []
    class Response:
        status, headers = 200, {"Content-Type": "application/json"}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, amount):
            assert amount == 65537
            return b"{}"
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            assert request.full_url == provider.PROVIDER_URL and timeout == 10
            assert request.get_header("Authorization") == "Bearer fake-test-key"
            assert request.get_header("User-agent") == "developers-eye/0.1"
            assert json.loads(request.data)["max_completion_tokens"] == 600
            assert json.loads(request.data)["reasoning_effort"] == "none"
            assert json.loads(request.data)["messages"][1]["content"] == content
            return Response()
    def opener(handler):
        assert isinstance(handler, provider.NoRedirect)
        return Opener()
    monkeypatch.setattr(provider, "build_opener", opener)
    assert provider._request(content)[0] == 200
    assert len(calls) == 1
