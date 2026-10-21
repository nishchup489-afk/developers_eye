"""Unit tests for the refactored, dependency-injected PolicyCoordinator.

Run from crawler/: poetry run pytest tests/test_policy_coordinator.py -v
The OneHopFetcher is mocked. No live HTTP, DNS, or database is accessed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import pytest

import crawler.policy_and_politeness.policy_coordinator as module
from crawler.fetcher.errors import FetcherSecurityError
from crawler.policy_and_politeness.dns_policy import (
    DNSResolutionError,
    UnsafeDestinationError,
)
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import (
    RobotsDecision,
    RobotsFetchResponse,
    RobotsPolicyResult,
)
from crawler.policy_and_politeness.policy_coordinator import (
    OneHopResponse,
    PolicyCoordinator,
    ResponseTooLargeError,
)


def run(coro):
    return asyncio.run(coro)


def test_coordinator_uses_fetchers_security_exception():
    assert module.FetcherSecurityError is FetcherSecurityError


@dataclass
class FakeOneHopFetcher:
    handler: object

    def __post_init__(self):
        self.calls = []

    async def fetch_once(self, *, url, approved_ips, max_body_bytes, timeout_seconds, user_agent):
        self.calls.append({
            "url": url,
            "approved_ips": approved_ips,
            "max_body_bytes": max_body_bytes,
            "timeout_seconds": timeout_seconds,
            "user_agent": user_agent,
        })
        response = self.handler(url)
        if asyncio.iscoroutine(response):
            response = await response
        if isinstance(response, BaseException):
            raise response
        return response


def manager(*, concurrency=2, interval=0, backoff=0.01):
    return PolitenessManager(
        max_concurrent_per_host=concurrency,
        min_interval_seconds=interval,
        default_backoff_seconds=backoff,
        max_backoff_seconds=30,
    )


@pytest.fixture
def env(monkeypatch):
    calls = {"dns": [], "robots": []}
    dns = {}
    robots_state = {"decision": RobotsDecision.ALLOW, "retry": None}

    async def resolve(host):
        calls["dns"].append(host)
        found = dns.get(host, ["93.184.215.14"])
        if isinstance(found, Exception):
            raise found
        return list(found)

    async def evaluate(session, url, fetcher, *, user_agent):
        calls["robots"].append((url, fetcher, user_agent))
        return RobotsPolicyResult(
            robots_state["decision"],
            "robots test",
            "https://example.com",
            robots_state["retry"],
        )

    monkeypatch.setattr(module, "resolve_safe_destination", resolve)
    monkeypatch.setattr(module, "evaluate_robots_policy", evaluate)

    def make(handler=None, *, allowed_hosts=None, **kwargs):
        fetcher = FakeOneHopFetcher(handler or (lambda _: OneHopResponse(200, {}, b"ok")))
        coord = PolicyCoordinator(
            allowed_hosts=allowed_hosts or ["example.com", "docs.example.com"],
            fetcher=fetcher,
            politeness_manager=kwargs.pop("politeness_manager", manager()),
            **kwargs,
        )
        return coord, fetcher

    return calls, dns, robots_state, make


def test_success_approved_ips_forwarded_to_fetcher(env):
    calls, _, _, make = env
    coordinator, fetcher = make(lambda _: OneHopResponse(200, {"Content-Type": "text/html"}, b"DOCS"))
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.ALLOW
    assert result.status_code == 200
    assert result.body == b"DOCS"
    assert result.redirect_chain == ("https://example.com/docs",)
    assert calls["dns"] == ["example.com"]
    assert calls["robots"][0][0] == "https://example.com/docs"
    assert fetcher.calls == [dict(
        url="https://example.com/docs",
        approved_ips=("93.184.215.14",),
        max_body_bytes=2_000_000,
        timeout_seconds=15.0,
        user_agent="DevelopersEyeBot",
    )]


@pytest.mark.parametrize("url", [
    "ftp://example.com/data", "https://example.com/has space",
    "https://evil.test/secret", "https://example.com:0/path",
    "http://user:pass@example.com/private",
])
def test_bad_urls_never_get_dns_or_network(env, url):
    calls, _, _, make = env
    coordinator, fetcher = make()
    result = run(coordinator.fetch(None, url))
    assert result.decision == RobotsDecision.DENY
    assert not fetcher.calls
    assert not calls["dns"]


def test_private_ip_blocked_before_fetch(env):
    calls, dns, _, make = env
    dns["example.com"] = UnsafeDestinationError("private IP")
    coordinator, fetcher = make()
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert fetcher.calls == []
    assert calls["robots"] == []


def test_dns_failure_deferred(env):
    _, dns, _, make = env
    dns["example.com"] = DNSResolutionError("timeout")
    coordinator, fetcher = make()
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DEFER
    assert result.retry_after_seconds == module.DEFAULT_DEFER_SECONDS
    assert not fetcher.calls


@pytest.mark.parametrize("decision", [RobotsDecision.DENY, RobotsDecision.DEFER])
def test_robots_blocks_network(env, decision):
    calls, _, robots_state, make = env
    robots_state.update(decision=decision, retry=23)
    coordinator, fetcher = make()
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == decision
    assert result.retry_after_seconds == 23
    assert not fetcher.calls
    assert len(calls["robots"]) == 1


def test_redirect_rechecks_host_dns_and_robots(env):
    calls, _, _, make = env
    def handler(url):
        return (OneHopResponse(301, {"LoCaTiOn": "https://docs.example.com/other"})
                if url == "https://example.com/docs"
                else OneHopResponse(200, {}, b"new"))
    coordinator, fetcher = make(handler)
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.ALLOW
    assert result.body == b"new"
    assert result.redirect_chain == (
        "https://example.com/docs", "https://docs.example.com/other",
    )
    assert calls["dns"] == ["example.com", "docs.example.com"]
    assert [row[0] for row in calls["robots"]] == [
        "https://example.com/docs", "https://docs.example.com/other",
    ]
    assert len(fetcher.calls) == 2


def test_unapproved_redirect_stops_before_second_request(env):
    calls, _, _, make = env
    coordinator, fetcher = make(lambda _: OneHopResponse(302, {"Location": "https://evil.test/private"}))
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert len(fetcher.calls) == 1
    assert calls["dns"] == ["example.com"]


def test_redirect_into_private_address_stops(env):
    calls, dns, _, make = env
    dns["docs.example.com"] = UnsafeDestinationError("unsafe")
    coordinator, fetcher = make(
        lambda _: OneHopResponse(302, {"location": "https://docs.example.com/secret"})
    )
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert len(fetcher.calls) == 1
    assert calls["dns"] == ["example.com", "docs.example.com"]


@pytest.mark.parametrize("location", [
    None, "https://example.com/docs", "http://example.com/cleartext",
])
def test_missing_location_loop_and_https_downgrade(env, location):
    _, _, _, make = env
    coordinator, fetcher = make(
        lambda _: OneHopResponse(302, {"Location": location} if location else {})
    )
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert len(fetcher.calls) == 1
    assert result.status_code == 302


def test_redirect_hop_limit(env):
    _, _, _, make = env
    coordinator, fetcher = make(
        lambda url: OneHopResponse(302, {"Location": url + "a"}),
        max_redirects=2,
    )
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert len(fetcher.calls) == 3
    assert len(result.redirect_chain) == 3


@pytest.mark.parametrize("status", [429, 503])
def test_rate_limit_defer_records_backoff(env, status):
    _, _, _, make = env
    coordinator, fetcher = make(
        lambda _: OneHopResponse(status, {"rEtRy-AfTeR": "4"}),
    )
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DEFER
    assert result.retry_after_seconds == 4
    assert coordinator.politeness._states["example.com"].backoff_until > 0
    assert len(fetcher.calls) == 1


@pytest.mark.parametrize("status, expected", [(500, "defer"), (502, "defer"), (404, "allow")])
def test_status_outcome(env, status, expected):
    _, _, _, make = env
    coordinator, _ = make(lambda _: OneHopResponse(status, {}, b"failure"))
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision(expected)


def test_network_error_deferred(env):
    _, _, _, make = env
    coordinator, _ = make(lambda _: httpx.ConnectTimeout("timeout"))
    result = run(coordinator.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DEFER


@pytest.mark.parametrize("exc", [
    ResponseTooLargeError("oversized"), FetcherSecurityError("rebind rejected"),
])
def test_security_or_size_error_denied_and_slot_freed(env, exc):
    _, _, _, make = env
    coord, _ = make(lambda _: exc)
    result = run(coord.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert coord.politeness._states["example.com"].semaphore._value == 2


def test_body_limit_catches_fake_fetcher_mistake(env):
    _, _, _, make = env
    coord, _ = make(lambda _: OneHopResponse(200, {}, b"too long"), max_body_bytes=2)
    result = run(coord.fetch(None, "https://example.com/docs"))
    assert result.decision == RobotsDecision.DENY
    assert coord.politeness._states["example.com"].semaphore._value == 2


def test_robots_fetch_bootstrap_without_self_recursion(env):
    calls, _, _, make = env
    coord, fetcher = make(lambda _: OneHopResponse(200, {}, b"User-agent: *\nDisallow: /private"))
    result = run(coord._fetch_robots("https://example.com/robots.txt"))
    assert result == RobotsFetchResponse(
        status_code=200, body="User-agent: *\nDisallow: /private", retry_after_seconds=None,
    )
    assert calls["dns"] == ["example.com"]
    assert calls["robots"] == []
    assert fetcher.calls[0]["max_body_bytes"] == module.MAX_ROBOTS_BYTES


def test_robots_redirect_rechecks_dns_and_host(env):
    calls, _, _, make = env
    coord, fetcher = make(lambda url:
        OneHopResponse(301, {"Location": "https://docs.example.com/robots.txt"})
        if url.startswith("https://example.com") else
        OneHopResponse(200, {}, b"User-agent: *\nAllow: /"))
    result = run(coord._fetch_robots("https://example.com/robots.txt"))
    assert result.status_code == 200
    assert calls["dns"] == ["example.com", "docs.example.com"]
    assert len(fetcher.calls) == 2


def test_robots_fetch_failure_becomes_robots_error(env):
    _, _, _, make = env
    coord, _ = make(lambda _: httpx.ConnectError("offline"))
    from crawler.policy_and_politeness.robots_policy import RobotsFetchError
    with pytest.raises(RobotsFetchError):
        run(coord._fetch_robots("https://example.com/robots.txt"))


def test_request_cancellation_frees_slot(env):
    _, _, _, make = env
    async def scenario():
        entered = asyncio.Event()
        async def hang(_):
            entered.set()
            await asyncio.Future()
        coord, _ = make(hang)
        task = asyncio.create_task(coord.fetch(None, "https://example.com/docs"))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert coord.politeness._states["example.com"].semaphore._value == 2
    run(scenario())


def test_two_hosts_have_distinct_slots(env):
    _, _, _, make = env
    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        active = set()
        maximum = [0]
        async def handle(url):
            active.add(url)
            maximum[0] = max(maximum[0], len(active))
            if len(active) == 2:
                started.set()
            await release.wait()
            active.remove(url)
            return OneHopResponse(200, {}, b"ok")
        coord, _ = make(handle, politeness_manager=manager(concurrency=1))
        first = asyncio.create_task(coord.fetch(None, "https://example.com/a"))
        second = asyncio.create_task(coord.fetch(None, "https://docs.example.com/b"))
        await asyncio.wait_for(started.wait(), timeout=1)
        release.set()
        results = await asyncio.gather(first, second)
        assert maximum[0] == 2
        assert all(result.decision == RobotsDecision.ALLOW for result in results)
    run(scenario())


@pytest.mark.parametrize("bad", [-1, True, 1.5])
def test_invalid_max_redirects_rejected(env, bad):
    _, _, _, make = env
    with pytest.raises(ValueError):
        make(max_redirects=bad)


@pytest.mark.parametrize("bad", [0, -1, True, 2.5])
def test_invalid_max_body_bytes_rejected(env, bad):
    _, _, _, make = env
    with pytest.raises(ValueError):
        make(max_body_bytes=bad)
