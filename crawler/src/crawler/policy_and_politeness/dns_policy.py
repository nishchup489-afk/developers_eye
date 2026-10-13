"""DNS and IP pinning for a public-only HTTPX crawler.

Tested with Python 3.13, HTTPX 0.28.1, HTTPCore 1.0.9.
This must be combined with the crawler's source allowlist, robots and path policies.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import AsyncIterator, Sequence
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlsplit

import httpcore
import httpx

from crawler.policy_and_politeness.host_policy import is_allowed_host, normalize_hostname


class UnsafeDestinationError(ValueError):
    """DNS returned a prohibited or unusable destination."""


class DNSResolutionError(OSError):
    """DNS lookup failed or timed out."""


def is_public_ip(address: str) -> bool:
    """Return True only for conservatively approved public IP literals."""
    if not isinstance(address, str) or not address or "%" in address:
        return False

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False

    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.sixtofour is not None or ip.teredo is not None:
            return False

    return ip.is_global and not ip.is_multicast and not ip.is_reserved


async def resolve_hostname(hostname: str, timeout: float = 5.0) -> list[str]:
    """Resolve IPv4/IPv6 TCP endpoints, without yet declaring them safe."""
    host = normalize_hostname(hostname) if isinstance(hostname, str) else None
    if host is None:
        raise DNSResolutionError("Invalid hostname")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        records = await asyncio.wait_for(
            loop.getaddrinfo(
                host,
                None,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            ),
            timeout=timeout,
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise DNSResolutionError(f"DNS lookup failed for {host}") from exc

    ips: list[str] = []
    seen: set[str] = set()
    for family, _socktype, _proto, _canonname, sockaddr in records:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        ip = sockaddr[0]
        if ip not in seen:
            seen.add(ip)
            ips.append(ip)
    return ips


def validate_dns_results(addresses: Sequence[str]) -> list[str]:
    """Reject the entire DNS answer if any returned address is unsafe."""
    if not addresses:
        raise UnsafeDestinationError("DNS returned no IP addresses")

    approved: list[str] = []
    seen: set[str] = set()
    for address in addresses:
        if not is_public_ip(address):
            raise UnsafeDestinationError(f"Unsafe DNS address: {address!r}")
        normalized = ipaddress.ip_address(address).compressed
        if normalized not in seen:
            seen.add(normalized)
            approved.append(normalized)
    return approved


async def resolve_safe_destination(hostname: str) -> list[str]:
    """DNS lookup plus fail-closed classification of every answer."""
    return validate_dns_results(await resolve_hostname(hostname))


class _PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    """Connect only to pre-approved numeric addresses for one hostname/port."""

    def __init__(self, host: str, port: int, ips: Sequence[str]) -> None:
        self.host = host
        self.port = port
        self.ips = tuple(ips)
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object = None,
    ) -> httpcore.AsyncNetworkStream:
        if normalize_hostname(host) != self.host or port != self.port:
            raise httpcore.ConnectError("Connection destination differs from approved origin")

        # Numeric IPs bypass hostname DNS in the HTTP transport.
        # Fall back only to other addresses from the validated DNS response.
        last_error: Exception | None = None
        for ip in self.ips:
            try:
                return await self.backend.connect_tcp(
                    host=ip,
                    port=port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is None:
            raise httpcore.ConnectError("No approved IP addresses available")
        raise last_error

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: object = None,
    ) -> httpcore.AsyncNetworkStream:
        raise httpcore.ConnectError("Unix sockets are not permitted")

    async def sleep(self, seconds: float) -> None:
        await self.backend.sleep(seconds)


_CORE_TO_HTTPX = (
    (httpcore.ConnectTimeout, httpx.ConnectTimeout),
    (httpcore.ReadTimeout, httpx.ReadTimeout),
    (httpcore.WriteTimeout, httpx.WriteTimeout),
    (httpcore.PoolTimeout, httpx.PoolTimeout),
    (httpcore.ConnectError, httpx.ConnectError),
    (httpcore.ReadError, httpx.ReadError),
    (httpcore.WriteError, httpx.WriteError),
    (httpcore.LocalProtocolError, httpx.LocalProtocolError),
    (httpcore.RemoteProtocolError, httpx.RemoteProtocolError),
    (httpcore.ProxyError, httpx.ProxyError),
)


@contextmanager
def _map_httpcore_errors() -> Iterator[None]:
    try:
        yield
    except httpcore.ProtocolError as exc:
        for core_type, httpx_type in _CORE_TO_HTTPX:
            if isinstance(exc, core_type):
                raise httpx_type(str(exc)) from exc
        raise httpx.ProtocolError(str(exc)) from exc
    except httpcore.NetworkError as exc:
        for core_type, httpx_type in _CORE_TO_HTTPX:
            if isinstance(exc, core_type):
                raise httpx_type(str(exc)) from exc
        raise httpx.NetworkError(str(exc)) from exc
    except httpcore.TimeoutException as exc:
        for core_type, httpx_type in _CORE_TO_HTTPX:
            if isinstance(exc, core_type):
                raise httpx_type(str(exc)) from exc
        raise httpx.TimeoutException(str(exc)) from exc


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, inner: AsyncIterator[bytes]) -> None:
        self.inner = inner

    async def __aiter__(self) -> AsyncIterator[bytes]:
        with _map_httpcore_errors():
            async for chunk in self.inner:
                yield chunk

    async def aclose(self) -> None:
        close = getattr(self.inner, "aclose", None)
        if close is not None:
            with _map_httpcore_errors():
                await close()


class PinnedHTTPTransport(httpx.AsyncBaseTransport):
    """HTTPX transport restricted to one URL and approved numeric IPs."""

    def __init__(self, url: str, approved_ips: Sequence[str]) -> None:
        try:
            parsed = urlsplit(url)
            host = normalize_hostname(parsed.hostname) if parsed.hostname else None
        except (ValueError, TypeError) as exc:
            raise UnsafeDestinationError("Malformed URL") from exc
        if host is None or not is_allowed_host(url, [host]):
            raise UnsafeDestinationError("Invalid URL or disallowed URL syntax")

        ips = validate_dns_results(approved_ips)
        self.host = host
        self.approved_url = httpx.URL(url)
        self.scheme = parsed.scheme.lower()
        self.port = parsed.port or {"http": 80, "https": 443}[self.scheme]
        self.pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=_PinnedNetworkBackend(self.host, self.port, ips),
            max_connections=10,
            max_keepalive_connections=0,
            retries=0,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if not is_allowed_host(url, [self.host]):
            raise UnsafeDestinationError("Request failed URL validation")
        if request.url != self.approved_url:
            raise UnsafeDestinationError("A new URL requires fresh policy and DNS checks")
        if request.url.scheme != self.scheme or request.url.port not in (None, self.port):
            raise UnsafeDestinationError("Request origin differs from approved origin")
        if "sni_hostname" in request.extensions:
            raise UnsafeDestinationError("Custom TLS server name is prohibited")

        # No custom Host header may route traffic to a different virtual host.
        expected_host = request.url.netloc.decode("ascii")
        if request.headers.get("host") != expected_host:
            raise UnsafeDestinationError("Host header differs from approved origin")

        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with _map_httpcore_errors():
            response = await self.pool.handle_async_request(core_request)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_ResponseStream(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self) -> None:
        await self.pool.aclose()


def safe_http_transport(url: str, approved_ips: Sequence[str]) -> httpx.AsyncBaseTransport:
    """Return HTTPX transport pinned to approved IP(s) for this URL's origin."""
    return PinnedHTTPTransport(url, approved_ips)
