"""httpcore-backed HTTPX transport that connects ONLY to approved numeric IPs.

IMPORTANT: Keep one transport / connection pool per fetch_once call. Reusing a
hostname-keyed pool across separately approved requests could reuse a socket
whose remote IP is no longer in that request's approved IP set.

Requires httpx >= 0.27 and httpcore >= 1.0, < 2.0. This intentionally uses the
public httpcore AsyncConnectionPool(network_backend=...) extension point.
"""

from __future__ import annotations

import ipaddress
import ssl
from collections.abc import AsyncIterator, Sequence

import httpcore
import httpx

from .errors import FetcherSecurityError


# Order specific subclasses before their parent exceptions.
_HTTP_ERROR_TYPES: tuple[tuple[type[Exception], type[httpx.HTTPError]], ...] = (
    (httpcore.ConnectTimeout, httpx.ConnectTimeout),
    (httpcore.ReadTimeout, httpx.ReadTimeout),
    (httpcore.WriteTimeout, httpx.WriteTimeout),
    (httpcore.PoolTimeout, httpx.PoolTimeout),
    (httpcore.ConnectError, httpx.ConnectError),
    (httpcore.ReadError, httpx.ReadError),
    (httpcore.WriteError, httpx.WriteError),
    (httpcore.RemoteProtocolError, httpx.RemoteProtocolError),
    (httpcore.LocalProtocolError, httpx.LocalProtocolError),
    (httpcore.ProxyError, httpx.ProxyError),
    (httpcore.UnsupportedProtocol, httpx.UnsupportedProtocol),
    (httpcore.TimeoutException, httpx.TimeoutException),
    (httpcore.NetworkError, httpx.NetworkError),
    (httpcore.ProtocolError, httpx.ProtocolError),
)
_CORE_EXCEPTIONS = tuple(core_type for core_type, _ in _HTTP_ERROR_TYPES)


def _convert_httpcore_exception(exc: Exception) -> Exception:
    for core_type, httpx_type in _HTTP_ERROR_TYPES:
        if isinstance(exc, core_type):
            return httpx_type(str(exc))
    return exc


def validate_approved_ips(approved_ips: Sequence[str]) -> tuple[str, ...]:
    """Reject non-IP destinations, private/loopback/link-local/reserved IPs.

    DNS policy remains responsible for choosing which IPs belong to the host;
    this is an additional fail-closed network-safety check.
    """
    if isinstance(approved_ips, (str, bytes)) or not approved_ips:
        raise FetcherSecurityError("approved_ips must contain at least one numeric IP")

    results: list[str] = []
    for raw in approved_ips:
        if not isinstance(raw, str) or not raw or "%" in raw:
            raise FetcherSecurityError("approved_ips must contain numeric IP addresses")
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise FetcherSecurityError(f"Non-numeric approved IP: {raw!r}") from exc
        if not ip.is_global:
            raise FetcherSecurityError(f"Non-public approved IP prohibited: {ip}")
        numeric = str(ip)
        if numeric not in results:
            results.append(numeric)
    return tuple(results)


class _PinnedBackend(httpcore.AsyncNetworkBackend):
    """Override hostname resolution at socket connect, not the HTTP Host/TLS SNI."""

    def __init__(self, expected_host: str, expected_port: int, approved_ips: tuple[str, ...]) -> None:
        self._expected_host = expected_host.casefold()
        self._expected_port = expected_port
        self._approved_ips = approved_ips
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        if host.casefold() != self._expected_host or port != self._expected_port:
            raise FetcherSecurityError("Unapproved connection hostname or port")
        if local_address is not None:
            raise FetcherSecurityError("Custom local bind addresses are disabled")

        last_error: Exception | None = None
        for numeric_ip in self._approved_ips:
            try:
                # AnyIO receives a numeric IP. No DNS lookup is performed here.
                return await self._backend.connect_tcp(
                    numeric_ip,
                    port,
                    timeout=timeout,
                    local_address=None,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        assert last_error is not None  # validated nonempty IP tuple
        raise last_error

    async def connect_unix_socket(self, path: str, timeout: float | None = None, socket_options=None):
        raise FetcherSecurityError("UNIX domain sockets are prohibited")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _CoreBodyStream(httpx.AsyncByteStream):
    def __init__(self, stream: AsyncIterator[bytes]) -> None:
        self._stream = stream

    async def __aiter__(self) -> AsyncIterator[bytes]:
        try:
            async for chunk in self._stream:
                yield chunk
        except _CORE_EXCEPTIONS as exc:
            raise _convert_httpcore_exception(exc) from exc

    async def aclose(self) -> None:
        try:
            if hasattr(self._stream, "aclose"):
                await self._stream.aclose()
        except _CORE_EXCEPTIONS as exc:
            raise _convert_httpcore_exception(exc) from exc


class PinnedAsyncTransport(httpx.AsyncBaseTransport):
    """One-URL, one-hop transport with no proxies, redirects, or IP re-resolution."""

    def __init__(
        self,
        *,
        expected_url: httpx.URL,
        approved_ips: Sequence[str],
    ) -> None:
        if expected_url.scheme not in ("http", "https") or not expected_url.host:
            raise FetcherSecurityError("Only absolute HTTP(S) URLs are supported")

        self._scheme = expected_url.scheme
        self._expected_url = expected_url
        self._host = expected_url.raw_host
        self._port = expected_url.port or (443 if self._scheme == "https" else 80)
        self._ips = validate_approved_ips(approved_ips)
        backend = _PinnedBackend(
            self._host.decode("ascii"),
            self._port,
            self._ips,
        )
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            proxy=None,
            retries=0,
            http1=True,
            http2=False,
            max_connections=1,
            max_keepalive_connections=0,
            network_backend=backend,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            raise FetcherSecurityError("Only GET requests are permitted")
        if (
            request.url.scheme != self._scheme
            or request.url.raw_host != self._host
            or (request.url.port or (443 if self._scheme == "https" else 80)) != self._port
        ):
            raise FetcherSecurityError("Request origin differs from approved origin")
        if request.url != self._expected_url:
            raise FetcherSecurityError("A different URL requires fresh policy checks")
        if request.headers.get("host") != self._expected_url.netloc.decode("ascii"):
            raise FetcherSecurityError("Host header differs from approved origin")
        if "sni_hostname" in request.extensions:
            raise FetcherSecurityError("Custom TLS server names are prohibited")
        # HTTPX retains the hostname in the request URL. httpcore therefore
        # uses that hostname as the Host authority and TLS certificate name.
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
        try:
            core_response = await self._pool.handle_async_request(core_request)
        except _CORE_EXCEPTIONS as exc:
            raise _convert_httpcore_exception(exc) from exc
        return httpx.Response(
            status_code=core_response.status,
            headers=core_response.headers,
            stream=_CoreBodyStream(core_response.stream),
            extensions=core_response.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()
