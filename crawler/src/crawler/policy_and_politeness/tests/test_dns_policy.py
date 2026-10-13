r"""Colorama-based offline tests for Developers Eye DNS/IP policy.

Place at crawler/src/crawler/robot/tests/test_dns_policy.py

From the developers-eye repository root (PowerShell):
    $env:PYTHONPATH = (Resolve-Path '.\crawler\src').Path
    poetry -C crawler run python -m crawler.robot.tests.test_dns_policy

No external DNS calls, network connections, or database are required.
Tested against the companion dns_policy.py implementation.
"""

from __future__ import annotations

import asyncio
import inspect
import socket
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import httpcore
import httpx
from colorama import Fore, Style, just_fix_windows_console

from crawler.policy_and_politeness import dns_policy as dns


@contextmanager
def expect_raises(error_type: type[BaseException]):
    try:
        yield
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__} but no exception was raised")


class Runner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def section(self, heading: str) -> None:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{heading}{Style.RESET_ALL}")

    async def check(self, title: str, test: Callable[[], Any]) -> None:
        try:
            result = test()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self.failed += 1
            print(f"{Fore.RED}[FAIL]{Style.RESET_ALL} {title}: {type(exc).__name__}: {exc}")
        else:
            self.passed += 1
            print(f"{Fore.GREEN}[PASS]{Style.RESET_ALL} {title}")

    def summary(self) -> int:
        total = self.passed + self.failed
        color = Fore.GREEN if self.failed == 0 else Fore.RED
        print(f"\n{color}{self.passed} passed, {self.failed} failed ({total} total){Style.RESET_ALL}")
        return 0 if self.failed == 0 else 1


def dns_record(ip: str) -> tuple:
    """Produce a synthetic getaddrinfo() record (never performs DNS)."""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    sockaddr = (ip, 0, 0, 0) if family == socket.AF_INET6 else (ip, 0)
    return family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr


async def test_resolve_records() -> None:
    records = [
        dns_record("8.8.8.8"),
        dns_record("2606:4700:4700::1111"),
        dns_record("8.8.8.8"),
    ]
    loop = asyncio.get_running_loop()
    mock = AsyncMock(return_value=records)
    with patch.object(loop, "getaddrinfo", mock):
        ips = await dns.resolve_hostname("DOCS.PYTHON.ORG.")
    assert ips == ["8.8.8.8", "2606:4700:4700::1111"], ips
    mock.assert_awaited_once_with(
        "docs.python.org",
        None,
        family=socket.AF_UNSPEC,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )


async def test_resolve_ip_literal() -> None:
    loop = asyncio.get_running_loop()
    mock = AsyncMock(side_effect=AssertionError("IP literals must not invoke DNS"))
    with patch.object(loop, "getaddrinfo", mock):
        assert await dns.resolve_hostname("8.8.8.8") == ["8.8.8.8"]
        assert await dns.resolve_hostname("2001:0db8::1") == ["2001:db8::1"]
    mock.assert_not_awaited()


async def test_resolve_empty_results() -> None:
    loop = asyncio.get_running_loop()
    with patch.object(loop, "getaddrinfo", AsyncMock(return_value=[])):
        assert await dns.resolve_hostname("docs.python.org") == []


async def test_resolve_dns_error() -> None:
    loop = asyncio.get_running_loop()
    with patch.object(loop, "getaddrinfo", AsyncMock(side_effect=socket.gaierror("NXDOMAIN"))):
        with expect_raises(dns.DNSResolutionError):
            await dns.resolve_hostname("docs.python.org")


async def test_resolve_timeout() -> None:
    loop = asyncio.get_running_loop()
    with patch.object(loop, "getaddrinfo", AsyncMock(side_effect=asyncio.TimeoutError())):
        with expect_raises(dns.DNSResolutionError):
            await dns.resolve_hostname("docs.python.org", timeout=0.1)


async def test_resolve_invalid_hostname() -> None:
    for bad in ("", "bad host.example", "-invalid.example", "bad\\host", None):
        with expect_raises(dns.DNSResolutionError):
            await dns.resolve_hostname(bad)


async def test_resolve_invalid_timeout() -> None:
    for timeout in (0, -1):
        with expect_raises(ValueError):
            await dns.resolve_hostname("docs.python.org", timeout=timeout)


async def test_safe_destination_all_public() -> None:
    mock = AsyncMock(return_value=["8.8.8.8", "1.1.1.1"])
    with patch.object(dns, "resolve_hostname", mock):
        assert await dns.resolve_safe_destination("docs.python.org") == ["8.8.8.8", "1.1.1.1"]
    mock.assert_awaited_once_with("docs.python.org")


async def test_safe_destination_mixed_addresses() -> None:
    with patch.object(dns, "resolve_hostname", AsyncMock(return_value=["8.8.8.8", "127.0.0.1"])):
        with expect_raises(dns.UnsafeDestinationError):
            await dns.resolve_safe_destination("docs.python.org")


async def test_safe_destination_empty() -> None:
    with patch.object(dns, "resolve_hostname", AsyncMock(return_value=[])):
        with expect_raises(dns.UnsafeDestinationError):
            await dns.resolve_safe_destination("docs.python.org")


async def test_safe_destination_propagates_dns_failure() -> None:
    with patch.object(dns, "resolve_hostname", AsyncMock(side_effect=dns.DNSResolutionError("failure"))):
        with expect_raises(dns.DNSResolutionError):
            await dns.resolve_safe_destination("docs.python.org")


async def transport_constructs() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    try:
        assert isinstance(transport, httpx.AsyncBaseTransport)
        assert transport.host == "docs.python.org"
        assert transport.port == 443
        assert list(transport.pool._network_backend.ips) == ["8.8.8.8"]
    finally:
        await transport.aclose()


async def test_valid_request() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    core = AsyncMock(return_value=httpcore.Response(200, content=b"offline test OK"))
    with patch.object(transport.pool, "handle_async_request", core):
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            response = await client.get("https://docs.python.org/3/")
    assert response.status_code == 200
    assert response.text == "offline test OK"
    forwarded_request = core.await_args.args[0]
    assert forwarded_request.url.host == b"docs.python.org"
    assert forwarded_request.url.target == b"/3/"
    assert any(
        key.lower() == b"host" and value == b"docs.python.org"
        for key, value in forwarded_request.headers
    )


async def test_blocked_request(new_url: str, headers: dict[str, str] | None = None) -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    core = AsyncMock(side_effect=AssertionError("Network must not be called"))
    with patch.object(transport.pool, "handle_async_request", core):
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            with expect_raises(dns.UnsafeDestinationError):
                await client.get(new_url, headers=headers)
    core.assert_not_awaited()


async def test_blocked_sni() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    core = AsyncMock(side_effect=AssertionError("Network must not be called"))
    with patch.object(transport.pool, "handle_async_request", core):
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            request = client.build_request("GET", "https://docs.python.org/3/")
            request.extensions["sni_hostname"] = "evil.example"
            with expect_raises(dns.UnsafeDestinationError):
                await client.send(request)
    core.assert_not_awaited()


async def test_redirect_is_revalidated() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    core = AsyncMock(return_value=httpcore.Response(
        302, headers=[(b"location", b"https://evil.example/")], content=b""
    ))
    with patch.object(transport.pool, "handle_async_request", core):
        async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=True) as client:
            with expect_raises(dns.UnsafeDestinationError):
                await client.get("https://docs.python.org/3/")
    assert core.await_count == 1, "Redirect must not send a second request"


class FakeNetworkBackend:
    def __init__(self, failed_ips: set[str] | None = None):
        self.failed_ips = failed_ips or set()
        self.calls: list[tuple[str, int]] = []
        self.stream = object()

    async def connect_tcp(self, *, host: str, port: int, **_kwargs: Any) -> object:
        self.calls.append((host, port))
        if host in self.failed_ips:
            raise httpcore.ConnectError("fake connection failure")
        return self.stream

    async def sleep(self, seconds: float) -> None:
        return None


async def test_pinned_connect_first_ip() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    try:
        backend = transport.pool._network_backend
        fake = FakeNetworkBackend()
        backend.backend = fake
        stream = await backend.connect_tcp("docs.python.org", 443)
        assert stream is fake.stream
        assert fake.calls == [("8.8.8.8", 443)], fake.calls
    finally:
        await transport.aclose()


async def test_pinned_connect_fallback() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8", "1.1.1.1"])
    try:
        backend = transport.pool._network_backend
        fake = FakeNetworkBackend(failed_ips={"8.8.8.8"})
        backend.backend = fake
        stream = await backend.connect_tcp("docs.python.org", 443)
        assert stream is fake.stream
        assert fake.calls == [("8.8.8.8", 443), ("1.1.1.1", 443)], fake.calls
    finally:
        await transport.aclose()


async def test_pinned_connect_all_fail() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8", "1.1.1.1"])
    try:
        backend = transport.pool._network_backend
        fake = FakeNetworkBackend(failed_ips={"8.8.8.8", "1.1.1.1"})
        backend.backend = fake
        with expect_raises(httpcore.ConnectError):
            await backend.connect_tcp("docs.python.org", 443)
        assert len(fake.calls) == 2
    finally:
        await transport.aclose()


async def test_pinned_connect_rejects_wrong_host_or_port() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    try:
        backend = transport.pool._network_backend
        fake = FakeNetworkBackend()
        backend.backend = fake
        with expect_raises(httpcore.ConnectError):
            await backend.connect_tcp("evil.example", 443)
        with expect_raises(httpcore.ConnectError):
            await backend.connect_tcp("docs.python.org", 8080)
        assert fake.calls == [], "No socket must be opened"
    finally:
        await transport.aclose()


async def test_no_unix_socket() -> None:
    transport = dns.safe_http_transport("https://docs.python.org/3/", ["8.8.8.8"])
    try:
        with expect_raises(httpcore.ConnectError):
            await transport.pool._network_backend.connect_unix_socket("/tmp/example.sock")
    finally:
        await transport.aclose()


IP_CASES: list[tuple[str, str | None, bool]] = [
    ("public IPv4 8.8.8.8", "8.8.8.8", True),
    ("public IPv4 1.1.1.1", "1.1.1.1", True),
    ("public IPv4 9.9.9.9", "9.9.9.9", True),
    ("private IPv4 10/8", "10.0.0.5", False),
    ("private IPv4 172.16/12", "172.20.1.2", False),
    ("private IPv4 192.168/16", "192.168.1.1", False),
    ("IPv4 loopback", "127.0.0.1", False),
    ("cloud metadata / link-local IPv4", "169.254.169.254", False),
    ("shared carrier address space", "100.64.0.1", False),
    ("unspecified IPv4", "0.0.0.0", False),
    ("IPv4 multicast", "224.0.0.1", False),
    ("limited broadcast", "255.255.255.255", False),
    ("IPv4 documentation range", "192.0.2.1", False),
    ("IPv4 benchmarking range", "198.18.0.1", False),
    ("public IPv6", "2606:4700:4700::1111", True),
    ("IPv6 loopback", "::1", False),
    ("IPv6 unspecified", "::", False),
    ("IPv6 unique-local", "fc00::1", False),
    ("IPv6 link-local", "fe80::1", False),
    ("IPv6 documentation range", "2001:db8::1", False),
    ("IPv6 multicast", "ff02::1", False),
    ("IPv4-mapped public IPv6", "::ffff:8.8.8.8", True),
    ("IPv4-mapped loopback IPv6", "::ffff:127.0.0.1", False),
    ("IPv4-mapped private IPv6", "::ffff:192.168.1.1", False),
    ("6to4 transition IPv6", "2002:c000:0201::1", False),
    ("Teredo transition IPv6", "2001:0:4136:e378:8000:63bf:3fff:fdd2", False),
    ("scoped IPv6 literal", "2606:4700:4700::1111%eth0", False),
    ("invalid address", "999.999.999.999", False),
    ("hostname is not IP", "docs.python.org", False),
    ("empty address", "", False),
    ("None instead of a string", None, False),
]


VALIDATION_CASES: list[tuple[str, list[str], list[str] | None]] = [
    ("single public address", ["8.8.8.8"], ["8.8.8.8"]),
    ("multiple public addresses", ["8.8.8.8", "1.1.1.1"], ["8.8.8.8", "1.1.1.1"]),
    ("deduplicate public addresses", ["8.8.8.8", "8.8.8.8"], ["8.8.8.8"]),
    ("normalize IPv6 notation", ["2606:4700:4700:0000:0000:0000:0000:1111"], ["2606:4700:4700::1111"]),
    ("reject empty DNS response", [], None),
    ("reject mixed public/private results", ["8.8.8.8", "192.168.1.5"], None),
    ("reject mixed public/loopback", ["8.8.8.8", "127.0.0.1"], None),
    ("reject invalid DNS address", ["8.8.8.8", "not-an-ip"], None),
    ("reject multicast DNS address", ["224.0.0.1"], None),
    ("reject cloud metadata DNS address", ["169.254.169.254"], None),
]


async def main() -> int:
    just_fix_windows_console()
    runner = Runner()

    runner.section("IP address safety (is_public_ip)")
    for name, address, expected in IP_CASES:
        def test_case(address: str | None = address, expected: bool = expected) -> None:
            actual = dns.is_public_ip(address)
            assert actual is expected, f"Expected {expected}, got {actual}"
        await runner.check(name, test_case)

    runner.section("DNS result validation (validate_dns_results)")
    for name, addresses, expected in VALIDATION_CASES:
        def test_case(addresses: list[str] = addresses, expected: list[str] | None = expected) -> None:
            if expected is None:
                with expect_raises(dns.UnsafeDestinationError):
                    dns.validate_dns_results(addresses)
            else:
                actual = dns.validate_dns_results(addresses)
                assert actual == expected, f"Expected {expected!r}, got {actual!r}"
        await runner.check(name, test_case)

    runner.section("Hostname resolution (resolve_hostname)")
    for name, test in [
        ("resolves A/AAAA and removes duplicates", test_resolve_records),
        ("IP literals bypass DNS", test_resolve_ip_literal),
        ("empty DNS response returns empty list", test_resolve_empty_results),
        ("DNS socket failure becomes DNSResolutionError", test_resolve_dns_error),
        ("DNS timeout becomes DNSResolutionError", test_resolve_timeout),
        ("malformed hostname rejected", test_resolve_invalid_hostname),
        ("invalid timeouts rejected", test_resolve_invalid_timeout),
    ]:
        await runner.check(name, test)

    runner.section("Combined DNS safety (resolve_safe_destination)")
    for name, test in [
        ("all public addresses accepted", test_safe_destination_all_public),
        ("one unsafe address rejects entire result", test_safe_destination_mixed_addresses),
        ("empty answer rejected", test_safe_destination_empty),
        ("DNS failure propagated", test_safe_destination_propagates_dns_failure),
    ]:
        await runner.check(name, test)

    runner.section("Transport construction (safe_http_transport)")
    await runner.check("valid origin and approved IPs", transport_constructs)
    for name, url, ips in [
        ("private destination rejected", "https://docs.python.org/3/", ["192.168.1.1"]),
        ("loopback destination rejected", "https://docs.python.org/3/", ["127.0.0.1"]),
        ("mixed public/private destinations rejected", "https://docs.python.org/3/", ["8.8.8.8", "10.0.0.2"]),
        ("empty approved IP list rejected", "https://docs.python.org/3/", []),
        ("embedded URL credentials rejected", "https://user:pass@docs.python.org/3/", ["8.8.8.8"]),
        ("nonstandard HTTPS port rejected", "https://docs.python.org:8443/3/", ["8.8.8.8"]),
        ("FTP scheme rejected", "ftp://docs.python.org/3/", ["8.8.8.8"]),
    ]:
        def constructor_rejection(url: str = url, ips: list[str] = ips) -> None:
            with expect_raises(dns.UnsafeDestinationError):
                dns.safe_http_transport(url, ips)
        await runner.check(name, constructor_rejection)

    runner.section("HTTPX request security (offline, mocked core)")
    await runner.check("approved request reaches core with original host", test_valid_request)
    for name, url, headers in [
        ("block unrelated hostname", "https://evil.example/", None),
        ("block same-host different path", "https://docs.python.org/other", None),
        ("block same-host different query", "https://docs.python.org/3/?page=2", None),
        ("block same-host different scheme", "http://docs.python.org/3/", None),
        ("block custom Host header", "https://docs.python.org/3/", {"Host": "evil.example"}),
    ]:
        await runner.check(name, lambda url=url, headers=headers: test_blocked_request(url, headers))
    await runner.check("block custom TLS SNI override", test_blocked_sni)
    await runner.check("redirect cannot escape approved origin", test_redirect_is_revalidated)

    runner.section("Pinned TCP connections (fully mocked network backend)")
    for name, test in [
        ("connect only to approved numeric IP", test_pinned_connect_first_ip),
        ("fallback uses only other approved IPs", test_pinned_connect_fallback),
        ("all approved IPs fail closed", test_pinned_connect_all_fail),
        ("reject wrong hostname or port before connect", test_pinned_connect_rejects_wrong_host_or_port),
        ("Unix domain sockets rejected", test_no_unix_socket),
    ]:
        await runner.check(name, test)

    return runner.summary()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
