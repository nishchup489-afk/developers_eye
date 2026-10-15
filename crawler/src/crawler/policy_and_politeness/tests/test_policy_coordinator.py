"""Unit tests for Developer's Eye PolicyCoordinator.

Run from your crawler directory:
    poetry run pytest tests/test_policy_coordinator.py -v

No live HTTP, DNS, or database is used. HTTPX MockTransport replaces socket
connections; a mocked robots-policy evaluator isolates orchestration.
"""

from __future__ import annotations

import asyncio
from collections import Counter

import httpx
import pytest

import crawler.policy_and_politeness.policy_coordinator as module
from crawler.policy_and_politeness.dns_policy import DNSResolutionError, UnsafeDestinationError
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import (
    RobotsDecision,
    RobotsFetchError,
    RobotsPolicyResult,
)
from crawler.policy_and_politeness.policy_coordinator import (
    PolicyCoordinator,
    ResponseTooLargeError,
)


@pytest.fixture
def setup(monkeypatch):
    """Mock the security inputs while still exercising actual coordinator code."""
    calls = {"dns": [], "transport": [], "robots": [], "http": []}
    handler = [lambda request: httpx.Response(200, content=b"OK")]
    dns_map: dict[str, list[str] | Exception] = {}
    robots_decision = [RobotsDecision.ALLOW]
    robots_delay = [None]

    async def resolve(host):
        calls["dns"].append(host)
        result = dns_map.get(host, ["93.184.215.14"])
        if isinstance(result, Exception):
            raise result
        return list(result)

    def transport(url, ips):
        calls["transport"].append((url, tuple(ips)))

        async def handle(request):
            calls["http"].append(request)
            result = handler[0](request)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        return httpx.MockTransport(handle)

    async def robots(session, url, fetcher, *, user_agent):
        calls["robots"].append((url, user_agent))
        return RobotsPolicyResult(robots_decision[0], "Test robots decision", "https://example.com", robots_delay[0])

    monkeypatch.setattr(module, "resolve_safe_destination", resolve)
    monkeypatch.setattr(module, "safe_http_transport", transport)
    monkeypatch.setattr(module, "evaluate_robots_policy", robots)
    return calls, handler, dns_map, robots_decision, robots_delay


def manager(*, concurrency=2, interval=0.0, backoff=0.01):
    return PolitenessManager(
        max_concurrent_per_host=concurrency,
        min_interval_seconds=interval,
        default_backoff_seconds=backoff,
        max_backoff_seconds=1.0,
    )


def coordinator(**kwargs):
    kwargs.setdefault("allowed_hosts", ["example.com", "docs.example.com"])
    kwargs.setdefault("politeness_manager", manager())
    return PolicyCoordinator(**kwargs)


def run(coro):
    return asyncio.run(coro)


def test_simple_success_get_pinned_and_robots(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(200, content=b"DOCS")
    c = coordinator()
    result = run(c.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.ALLOW
    assert result.body == b"DOCS"
    assert result.status_code == 200
    assert result.final_url == "https://example.com/docs"
    assert result.redirect_chain == ("https://example.com/docs",)
    assert calls["robots"] == [("https://example.com/docs", "DevelopersEyeBot")]
    assert calls["dns"] == ["example.com"]
    assert calls["transport"] == [("https://example.com/docs", ("93.184.215.14",))]
    assert calls["http"][0].method == "GET"
    assert calls["http"][0].headers["user-agent"] == "DevelopersEyeBot"


@pytest.mark.parametrize("url", [
    "ftp://example.com/path", "http://user:pw@example.com/", "https://example.com/no space",
    "https://example.com:0/docs", "https://example.com\\@evil.test/",
])
def test_invalid_url_denied_before_dns(setup, url):
    calls, *_ = setup
    result = run(coordinator().fetch(None, url))
    assert result.decision == RobotsDecision.DENY
    assert calls["dns"] == []
    assert calls["http"] == []


def test_host_rejected_before_dns_or_robots(setup):
    calls, *_ = setup
    result = run(coordinator().fetch(None, "https://evil.test/internal"))
    assert result.decision == RobotsDecision.DENY
    assert calls["dns"] == []
    assert calls["robots"] == []
    assert calls["http"] == []


def test_private_ip_denied(setup):
    calls, _, dns, *_ = setup
    dns["example.com"] = UnsafeDestinationError("Unsafe DNS address: 127.0.0.1")
    result = run(coordinator().fetch(None, "https://example.com/x"))
    assert result.decision == RobotsDecision.DENY
    assert calls["http"] == []


def test_dns_failure_deferred(setup):
    calls, _, dns, *_ = setup
    dns["example.com"] = DNSResolutionError("timeout")
    result = run(coordinator().fetch(None, "https://example.com/x"))
    assert result.decision == RobotsDecision.DEFER
    assert result.retry_after_seconds is not None
    assert calls["robots"] == []


@pytest.mark.parametrize("decision", [RobotsDecision.DENY, RobotsDecision.DEFER])
def test_robots_restrictions_prevent_page_fetch(setup, decision):
    calls, _, _, robots, delay = setup
    robots[0] = decision
    delay[0] = 17 if decision == RobotsDecision.DEFER else None
    result = run(coordinator().fetch(None, "https://example.com/docs"))
    assert result.decision == decision
    assert result.retry_after_seconds == delay[0]
    assert calls["http"] == []


def test_relative_redirect_rechecks_all_policies(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: (
        httpx.Response(302, headers={"Location": "/new"})
        if r.url.path == "/old" else httpx.Response(200, content=b"NEW")
    )
    result = run(coordinator().fetch(None, "https://example.com/old"))
    assert result.decision == RobotsDecision.ALLOW
    assert result.body == b"NEW"
    assert result.redirect_chain == ("https://example.com/old", "https://example.com/new")
    assert calls["dns"] == ["example.com", "example.com"]
    assert len(calls["robots"]) == 2
    assert len(calls["transport"]) == 2


def test_cross_host_allowed_redirect_rechecks_other_dns(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: (
        httpx.Response(301, headers={"Location": "https://docs.example.com/new"})
        if r.url.host == "example.com" else httpx.Response(200, content=b"DONE")
    )
    result = run(coordinator().fetch(None, "https://example.com/old"))
    assert result.decision == RobotsDecision.ALLOW
    assert calls["dns"] == ["example.com", "docs.example.com"]
    assert calls["robots"][1][0] == "https://docs.example.com/new"


def test_redirect_to_unapproved_host_is_never_requested(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(301, headers={"Location": "https://evil.test/secret"})
    result = run(coordinator().fetch(None, "https://example.com/start"))
    assert result.decision == RobotsDecision.DENY
    assert calls["dns"] == ["example.com"]
    assert len(calls["http"]) == 1
    assert result.final_url == "https://evil.test/secret"


def test_redirect_to_private_ip_is_denied(setup):
    calls, handler, dns, *_ = setup
    handler[0] = lambda r: httpx.Response(302, headers={"Location": "https://docs.example.com/private"})
    dns["docs.example.com"] = UnsafeDestinationError("private IP")
    result = run(coordinator().fetch(None, "https://example.com/start"))
    assert result.decision == RobotsDecision.DENY
    assert calls["dns"] == ["example.com", "docs.example.com"]
    assert len(calls["http"]) == 1


@pytest.mark.parametrize("location", [None, "https://example.com/start", "http://example.com/new"])
def test_redirect_invalid_loop_or_downgrade_stops(setup, location):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(302, headers={"Location": location} if location else {})
    result = run(coordinator().fetch(None, "https://example.com/start"))
    assert result.decision == RobotsDecision.DENY
    assert result.status_code == 302
    assert len(calls["http"]) == 1


def test_redirect_hop_limit(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(
        302, headers={"Location": f"/page{int(r.url.path.removeprefix('/page') or 0)+1}"}
    )
    result = run(coordinator(max_redirects=2).fetch(None, "https://example.com/page0"))
    assert result.decision == RobotsDecision.DENY
    assert result.redirect_chain == (
        "https://example.com/page0", "https://example.com/page1", "https://example.com/page2"
    )
    assert len(calls["http"]) == 3


@pytest.mark.parametrize("status", [429, 503])
def test_rate_limit_response_deferred_and_records_backoff(setup, status):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(status, headers={"Retry-After": "1"})
    c = coordinator()
    result = run(c.fetch(None, "https://example.com/start"))
    assert result.decision == RobotsDecision.DEFER
    assert result.status_code == status
    assert result.retry_after_seconds == 1.0
    assert c.politeness._states["example.com"].backoff_until > 0
    assert len(calls["http"]) == 1


def test_http_404_is_not_a_policy_denial(setup):
    _, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(404, content=b"missing")
    result = run(coordinator().fetch(None, "https://example.com/no-page"))
    assert result.decision == RobotsDecision.ALLOW
    assert result.status_code == 404
    assert result.body == b"missing"


def test_http_500_deferred(setup):
    _, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(500, content=b"server broken")
    result = run(coordinator().fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DEFER
    assert result.status_code == 500


def test_too_large_response_denied_and_slot_released(setup):
    _, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(200, content=b"12345")
    c = coordinator(max_body_bytes=4, politeness_manager=manager(concurrency=1))

    async def exercise():
        first = await c.fetch(None, "https://example.com/docs")
        second = await asyncio.wait_for(c.fetch(None, "https://example.com/docs"), timeout=.5)
        assert first.decision == second.decision == RobotsDecision.DENY
        assert "exceeded" in first.reason.lower()

    run(exercise())


def test_http_connection_error_deferred_releases_slot(setup):
    _, handler, *_ = setup
    handler[0] = lambda r: (_ for _ in ()).throw(httpx.ConnectError("connection refused"))
    c = coordinator(politeness_manager=manager(concurrency=1))
    async def exercise():
        one = await c.fetch(None, "https://example.com/x")
        two = await asyncio.wait_for(c.fetch(None, "https://example.com/x"), timeout=.5)
        assert one.decision == two.decision == RobotsDecision.DEFER
    run(exercise())


def test_cancellation_releases_slot(setup):
    _, handler, *_ = setup
    arrived = asyncio.Event()
    async def delayed(r):
        arrived.set()
        await asyncio.Event().wait()
    handler[0] = delayed
    c = coordinator(politeness_manager=manager(concurrency=1))

    async def exercise():
        task = asyncio.create_task(c.fetch(None, "https://example.com/x"))
        await asyncio.wait_for(arrived.wait(), timeout=.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        handler[0] = lambda r: httpx.Response(200, content=b"RESUMED")
        subsequent = await asyncio.wait_for(c.fetch(None, "https://example.com/x"), timeout=.5)
        assert subsequent.body == b"RESUMED"

    run(exercise())


def test_per_host_concurrency_limit(setup):
    _, handler, *_ = setup
    active = 0
    high = 0
    async def delayed(r):
        nonlocal active, high
        active += 1
        high = max(high, active)
        await asyncio.sleep(.02)
        active -= 1
        return httpx.Response(200, content=b"OK")
    handler[0] = delayed
    c = coordinator(politeness_manager=manager(concurrency=2))
    async def exercise():
        results = await asyncio.gather(*(
            c.fetch(None, f"https://example.com/{i}") for i in range(7)
        ))
        assert all(r.decision == RobotsDecision.ALLOW for r in results)
    run(exercise())
    assert high == 2


def test_constructor_rejects_invalid_parameters():
    cases = [
        {"allowed_hosts": []},
        {"allowed_hosts": "example.com"},
        {"allowed_hosts": ["example.com"], "max_body_bytes": 0},
        {"allowed_hosts": ["example.com"], "timeout_seconds": float("nan")},
        {"allowed_hosts": ["example.com"], "max_redirects": True},
        {"allowed_hosts": ["example.com"], "user_agent": ""},
    ]
    for args in cases:
        with pytest.raises(ValueError):
            PolicyCoordinator(**args)


def test_robots_fetch_is_ip_pinned_and_has_no_recursive_robots_check(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(200, content=b"User-agent: *\nDisallow: /blocked")
    fetched = run(coordinator()._fetch_robots("https://example.com/robots.txt"))
    assert fetched.status_code == 200
    assert "Disallow" in fetched.body
    assert calls["dns"] == ["example.com"]
    assert calls["robots"] == []
    assert calls["transport"] == [("https://example.com/robots.txt", ("93.184.215.14",))]


def test_robots_cross_host_redirect_rechecked(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: (
        httpx.Response(302, headers={"Location": "https://docs.example.com/robots2.txt"})
        if r.url.host == "example.com" else httpx.Response(200, content=b"User-agent: *\nAllow: /")
    )
    got = run(coordinator()._fetch_robots("https://example.com/robots.txt"))
    assert got.status_code == 200
    assert calls["dns"] == ["example.com", "docs.example.com"]
    assert len(calls["transport"]) == 2


def test_robots_unsafe_redirect_fails_closed(setup):
    calls, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(301, headers={"Location": "https://evil.test/robots.txt"})
    with pytest.raises(RobotsFetchError):
        run(coordinator()._fetch_robots("https://example.com/robots.txt"))
    assert calls["dns"] == ["example.com"]
    assert len(calls["http"]) == 1


def test_robots_oversize_fails_closed(setup):
    _, handler, *_ = setup
    handler[0] = lambda r: httpx.Response(200, content=b"x" * (module.MAX_ROBOTS_BYTES + 1))
    with pytest.raises(RobotsFetchError):
        run(coordinator()._fetch_robots("https://example.com/robots.txt"))
