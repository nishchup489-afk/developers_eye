"""Offline tests for Developer's Eye's HTTPXHopFetcher and pinned transport.

Run from the crawler/ directory:
    poetry run pytest tests/test_fetcher.py -q -s

No real HTTP or DNS traffic is generated. MockTransport exercises fetch.py;
fake HTTPCore pools/backends exercise the IP-pinned transport boundaries.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpcore
import httpx
import pytest

import crawler.fetcher.fetch as fetch_mod
import crawler.fetcher.transport as transport_mod
from crawler.fetcher.client import create_pinned_client
from crawler.fetcher.config import DEFAULT_CHUNK_SIZE, FetcherConfig
from crawler.fetcher.errors import FetcherSecurityError, ResponseTooLargeError
from crawler.fetcher.fetch import HTTPXHopFetcher
from crawler.fetcher.schemas import OneHopResponse
from crawler.fetcher.transport import (
    PinnedAsyncTransport,
    _CoreBodyStream,
    _PinnedBackend,
    _convert_httpcore_exception,
    validate_approved_ips,
)

URL = "https://example.com/docs"
IP = "1.1.1.1"


def run(coro):
    """Run async test cases without requiring pytest-asyncio."""
    return asyncio.run(coro)


class RecordingStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.read_chunks = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.read_chunks += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def install_mock_client(monkeypatch, handler):
    """Keep the real fetch_once code but replace its network client."""
    configs: list[dict[str, Any]] = []

    def factory(*, url, approved_ips, timeout_seconds):
        configs.append({"url": url, "ips": approved_ips, "timeout": timeout_seconds})
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            trust_env=False,
            timeout=timeout_seconds,
        )

    monkeypatch.setattr(fetch_mod, "create_pinned_client", factory)
    return configs


async def fetch(*, max_body_bytes=128, timeout_seconds=1.0, user_agent="DevelopersEyeBot", approved_ips=(IP,), url=URL, config=None):
    return await HTTPXHopFetcher(config).fetch_once(
        url=url,
        approved_ips=approved_ips,
        max_body_bytes=max_body_bytes,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )


# -------------------- Configuration and IP validation --------------------


def test_chunk_size_is_16_kib():
    assert DEFAULT_CHUNK_SIZE == 16 * 1024 == 16_384


@pytest.mark.parametrize("size", [0, -1, True, 1.5, "16"])
def test_reject_invalid_chunk_size(size):
    with pytest.raises(ValueError):
        FetcherConfig(chunk_size=size)


def test_media_types_and_suffixes():
    config = FetcherConfig()
    assert config.permits_media_type("text/html; charset=UTF-8")
    assert config.permits_media_type("application/problem+json")
    assert config.permits_media_type("application/custom+xml")
    assert config.permits_media_type("APPLICATION/JSON")
    assert not config.permits_media_type("image/png")
    assert not config.permits_media_type("application/octet-stream")
    assert not config.permits_media_type(None)


def test_media_type_config_validation():
    with pytest.raises(ValueError):
        FetcherConfig(allowed_media_types=frozenset())
    with pytest.raises(ValueError):
        FetcherConfig(allowed_media_types={"text/html"})


def test_public_ip_deduplication_ipv4_and_ipv6():
    assert validate_approved_ips(["1.1.1.1", "1.1.1.1", "2606:4700:4700::1111"]) == (
        "1.1.1.1", "2606:4700:4700::1111"
    )


@pytest.mark.parametrize("addresses", [
    [], "1.1.1.1", ["localhost"], ["127.0.0.1"], ["10.0.0.1"],
    ["192.168.1.5"], ["169.254.0.1"], ["::1"], ["fe80::1"],
    ["1.1.1.1%eth0"], ["8.8.8.8", "127.0.0.1"], [None],
])
def test_bad_ip_lists_are_rejected(addresses):
    with pytest.raises(FetcherSecurityError):
        validate_approved_ips(addresses)


# -------------------- HTTPXHopFetcher: real logic, fake HTTP transport --------------------


def test_200_html_returns_body_headers_and_expected_request(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"<h1>Docs</h1>")

    configs = install_mock_client(monkeypatch, handler)
    response = run(fetch())
    assert isinstance(response, OneHopResponse)
    assert response.status_code == 200
    assert response.body == b"<h1>Docs</h1>"
    assert response.headers["content-type"] == "text/html"
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].headers["user-agent"] == "DevelopersEyeBot"
    assert seen[0].headers["accept-encoding"] == "identity"
    assert "application/json" in seen[0].headers["accept"]
    assert configs == [{"url": URL, "ips": (IP,), "timeout": 1.0}]


@pytest.mark.parametrize("status", [201, 204, 301, 302, 303, 307, 308, 404, 410, 429, 503])
def test_non_200_returns_headers_without_reading_body(monkeypatch, status):
    stream = RecordingStream([b"not needed"])
    called = []

    def handler(request):
        called.append(str(request.url))
        return httpx.Response(
            status, headers={"Location": "/next", "Retry-After": "60"}, stream=stream
        )

    install_mock_client(monkeypatch, handler)
    response = run(fetch())
    assert response.status_code == status
    assert response.body == b""
    assert stream.read_chunks == 0
    assert stream.closed
    assert called == [URL]  # Follow redirects is disabled.


def test_content_type_missing_skips_body(monkeypatch):
    stream = RecordingStream([b"binary"])
    install_mock_client(monkeypatch, lambda req: httpx.Response(200, stream=stream))
    assert run(fetch()).body == b""
    assert stream.read_chunks == 0 and stream.closed


def test_unsupported_content_type_skips_body(monkeypatch):
    stream = RecordingStream([b"\x89PNG..."])
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(200, headers={"Content-Type": "image/png"}, stream=stream),
    )
    assert run(fetch()).body == b""
    assert stream.read_chunks == 0 and stream.closed


def test_json_is_accepted(monkeypatch):
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(
            200, headers={"Content-Type": "application/problem+json"}, content=b'{"ok":true}'
        ),
    )
    assert run(fetch()).body == b'{"ok":true}'


def test_small_chunks_join_correctly(monkeypatch):
    stream = RecordingStream([b"abc", b"de", b"fghi"])
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(200, headers={"Content-Type": "text/plain"}, stream=stream),
    )
    response = run(fetch(max_body_bytes=9, config=FetcherConfig(chunk_size=2)))
    assert response.body == b"abcdefghi"
    assert stream.closed


def test_declared_content_length_larger_than_limit_rejected_before_read(monkeypatch):
    stream = RecordingStream([b"x" * 100])
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(
            200,
            headers={"Content-Type": "text/html", "Content-Length": "100"},
            stream=stream,
        ),
    )
    with pytest.raises(ResponseTooLargeError):
        run(fetch(max_body_bytes=10))
    assert stream.read_chunks == 0
    assert stream.closed


def test_streaming_overflow_stops_and_closes(monkeypatch):
    stream = RecordingStream([b"12345", b"67890", b"excess"])
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(200, headers={"Content-Type": "text/plain"}, stream=stream),
    )
    with pytest.raises(ResponseTooLargeError):
        run(fetch(max_body_bytes=10))
    assert stream.closed


@pytest.mark.parametrize("declared", ["-2", "nope", "2.5", " 10 "])
def test_malformed_content_length_rejected(monkeypatch, declared):
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(
            200, headers={"Content-Type": "text/html", "Content-Length": declared}, content=b"ok"
        ),
    )
    with pytest.raises(FetcherSecurityError):
        run(fetch())


def test_unexpected_compression_rejected(monkeypatch):
    install_mock_client(
        monkeypatch,
        lambda req: httpx.Response(
            200, headers={"Content-Type": "text/html", "Content-Encoding": "gzip"}, content=b"x"
        ),
    )
    with pytest.raises(FetcherSecurityError):
        run(fetch())


def test_httpx_read_timeout_propagates(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("simulated timeout", request=request)

    install_mock_client(monkeypatch, handler)
    with pytest.raises(httpx.ReadTimeout):
        run(fetch())


def test_total_deadline_times_out(monkeypatch):
    async def slow_handler(request):
        await asyncio.sleep(0.05)
        return httpx.Response(200, headers={"Content-Type": "text/plain"}, content=b"late")

    install_mock_client(monkeypatch, slow_handler)
    with pytest.raises(TimeoutError):
        run(fetch(timeout_seconds=0.005))


@pytest.mark.parametrize("kwargs", [
    {"max_body_bytes": 0}, {"max_body_bytes": True},
    {"timeout_seconds": -1}, {"timeout_seconds": float("nan")},
    {"user_agent": ""}, {"user_agent": "Bot\r\nHost: attacker"},
    {"approved_ips": ["127.0.0.1"]}, {"url": "ftp://example.com/"},
])
def test_invalid_fetch_arguments_fail_before_network(monkeypatch, kwargs):
    def no_network(**unused):
        raise AssertionError("network client must not be constructed")

    monkeypatch.setattr(fetch_mod, "create_pinned_client", no_network)
    with pytest.raises((ValueError, FetcherSecurityError)):
        run(fetch(**kwargs))


# -------------------- _PinnedBackend and stream adapter --------------------


class FakeSocketBackend:
    def __init__(self, failures: set[str] | None = None):
        self.failures = failures or set()
        self.calls: list[tuple[str, int]] = []
        self.sleeps: list[float] = []

    async def connect_tcp(self, host, port, **kwargs):
        self.calls.append((host, port))
        if host in self.failures:
            raise httpcore.ConnectError("unavailable")
        return (host, port)

    async def sleep(self, seconds):
        self.sleeps.append(seconds)


def test_backend_uses_numeric_ip_and_fallback():
    backend = _PinnedBackend("example.com", 443, ("1.1.1.1", "8.8.8.8"))
    fake = FakeSocketBackend(failures={"1.1.1.1"})
    backend._backend = fake
    assert run(backend.connect_tcp("EXAMPLE.COM", 443)) == ("8.8.8.8", 443)
    assert fake.calls == [("1.1.1.1", 443), ("8.8.8.8", 443)]


def test_backend_all_connections_failed():
    backend = _PinnedBackend("example.com", 443, ("1.1.1.1", "8.8.8.8"))
    backend._backend = FakeSocketBackend(failures={"1.1.1.1", "8.8.8.8"})
    with pytest.raises(httpcore.ConnectError):
        run(backend.connect_tcp("example.com", 443))


@pytest.mark.parametrize("host,port,local", [
    ("other.example", 443, None), ("example.com", 8443, None),
    ("example.com", 443, "127.0.0.1"),
])
def test_backend_rejects_unapproved_destination(host, port, local):
    backend = _PinnedBackend("example.com", 443, (IP,))
    backend._backend = FakeSocketBackend()
    with pytest.raises(FetcherSecurityError):
        run(backend.connect_tcp(host, port, local_address=local))
    assert backend._backend.calls == []


def test_backend_rejects_unix_sockets():
    backend = _PinnedBackend("example.com", 443, (IP,))
    with pytest.raises(FetcherSecurityError):
        run(backend.connect_unix_socket("/tmp/internal.sock"))


def test_backend_sleep_delegates():
    backend = _PinnedBackend("example.com", 443, (IP,))
    fake = FakeSocketBackend()
    backend._backend = fake
    run(backend.sleep(1.25))
    assert fake.sleeps == [1.25]


def test_httpcore_exception_conversion():
    assert isinstance(_convert_httpcore_exception(httpcore.ConnectTimeout("x")), httpx.ConnectTimeout)
    assert isinstance(_convert_httpcore_exception(httpcore.ReadTimeout("x")), httpx.ReadTimeout)
    assert isinstance(_convert_httpcore_exception(httpcore.ConnectError("x")), httpx.ConnectError)


def test_core_body_stream_yields_and_closes():
    class Source:
        closed = False

        async def __aiter__(self):
            yield b"one"
            yield b"two"

        async def aclose(self):
            self.closed = True

    source = Source()
    stream = _CoreBodyStream(source)

    async def exercise():
        data = [chunk async for chunk in stream]
        await stream.aclose()
        return data

    assert run(exercise()) == [b"one", b"two"]
    assert source.closed


def test_core_body_stream_maps_read_error():
    class BrokenSource:
        async def __aiter__(self):
            raise httpcore.ReadTimeout("stream timed out")
            yield b"never"

    stream = _CoreBodyStream(BrokenSource())

    async def consume():
        return [chunk async for chunk in stream]

    with pytest.raises(httpx.ReadTimeout):
        run(consume())


# -------------------- HTTPX-to-HTTPCore transport bridge --------------------


class FakeCorePool:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.requests = []
        self.closed = False
        self.result = httpcore.Response(
            status=200, headers=[(b"content-type", b"text/plain")], content=b"ok"
        )

    async def handle_async_request(self, request):
        self.requests.append(request)
        return self.result

    async def aclose(self):
        self.closed = True


def make_fake_transport(monkeypatch, expected_url=URL):
    pools = []

    def factory(**kwargs):
        pool = FakeCorePool(**kwargs)
        pools.append(pool)
        return pool

    monkeypatch.setattr(transport_mod.httpcore, "AsyncConnectionPool", factory)
    transport = PinnedAsyncTransport(expected_url=httpx.URL(expected_url), approved_ips=(IP,))
    return transport, pools[0]


def test_pinned_transport_checks_get_and_origin(monkeypatch):
    transport, pool = make_fake_transport(monkeypatch)
    assert pool.kwargs["max_connections"] == 1
    assert pool.kwargs["max_keepalive_connections"] == 0
    assert pool.kwargs["retries"] == 0
    assert pool.kwargs["proxy"] is None
    assert isinstance(pool.kwargs["network_backend"], _PinnedBackend)

    with pytest.raises(FetcherSecurityError):
        run(transport.handle_async_request(httpx.Request("POST", URL)))
    with pytest.raises(FetcherSecurityError):
        run(transport.handle_async_request(httpx.Request("GET", "https://other.example/docs")))
    with pytest.raises(FetcherSecurityError):
        run(transport.handle_async_request(httpx.Request("GET", "http://example.com/docs")))
    assert pool.requests == []
    run(transport.aclose())
    assert pool.closed


def test_pinned_transport_preserves_hostname_for_http_and_tls(monkeypatch):
    transport, pool = make_fake_transport(monkeypatch)
    response = run(transport.handle_async_request(httpx.Request("GET", URL)))
    assert response.status_code == 200
    core_request = pool.requests[0]
    assert core_request.url.host == b"example.com"
    assert core_request.url.scheme == b"https"
    assert core_request.url.target == b"/docs"
    run(transport.aclose())


def test_client_disables_redirects_and_environment_proxies(monkeypatch):
    class DummyTransport(httpx.AsyncBaseTransport):
        def __init__(self, *, expected_url, approved_ips):
            self.approved_ips = approved_ips
            self.expected_url = expected_url

        async def handle_async_request(self, request):
            return httpx.Response(302, headers={"Location": "/new"})

        async def aclose(self):
            pass

    import crawler.fetcher.client as client_mod
    monkeypatch.setattr(client_mod, "PinnedAsyncTransport", DummyTransport)

    async def exercise():
        async with create_pinned_client(url=URL, approved_ips=(IP,), timeout_seconds=1) as client:
            assert not client.follow_redirects
            assert client.max_redirects == 0
            assert isinstance(client._transport, DummyTransport)
            response = await client.get(URL)
            return response

    response = run(exercise())
    assert response.status_code == 302
    assert response.next_request is not None


# Known security gaps: keep as strict xfails until fixed in transport.py.
# They become XPASS (a failing suite) once implementation changes, prompting
# removal of xfail and promotion to regular tests.
@pytest.mark.xfail(strict=True, reason="transport.py currently accepts a custom Host header")
def test_security_rejects_custom_host_header(monkeypatch):
    transport, pool = make_fake_transport(monkeypatch)
    request = httpx.Request("GET", URL, headers={"Host": "attacker.example"})
    with pytest.raises(FetcherSecurityError):
        run(transport.handle_async_request(request))


@pytest.mark.xfail(strict=True, reason="transport.py currently forwards a custom TLS SNI extension")
def test_security_rejects_custom_sni_extension(monkeypatch):
    transport, pool = make_fake_transport(monkeypatch)
    request = httpx.Request("GET", URL, extensions={"sni_hostname": "attacker.example"})
    with pytest.raises(FetcherSecurityError):
        run(transport.handle_async_request(request))


@pytest.mark.xfail(strict=True, reason="transport.py currently checks the origin rather than the exact approved URL")
def test_security_rejects_other_path_on_same_host(monkeypatch):
    transport, pool = make_fake_transport(monkeypatch)
    request = httpx.Request("GET", "https://example.com/admin")
    with pytest.raises(FetcherSecurityError):
        run(transport.handle_async_request(request))
