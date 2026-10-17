# from urllib.parse import urlsplit 

# url = "HTTPS://EXAMPLE.COM:443/docs?lang=en#intro"

# print(urlsplit(url))


# import unicodedata 

# print(unicodedata.category("A"))
# print(unicodedata.category("5"))
# print(unicodedata.category("\\"))

# import unicodedata

# char = "\u200B"  # Zero-width space

# print(unicodedata.category(char))  # Cf


# from urllib.parse import urlsplit

# url = "https://attacker.example\\@docs.python.org/secret"

# print(urlsplit(url).hostname)
# docs.python.org


# hostname = "docs.python.org."

# host = hostname.removesuffix(".")

# print(host)
# # docs.python.org

#  bt65


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
        except httpcore.HTTPError as exc:
            raise _convert_httpcore_exception(exc) from exc

    async def aclose(self) -> None:
        try:
            if hasattr(self._stream, "aclose"):
                await self._stream.aclose()
        except httpcore.HTTPError as exc:
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
        except httpcore.HTTPError as exc:
            raise _convert_httpcore_exception(exc) from exc
        return httpx.Response(
            status_code=core_response.status,
            headers=core_response.headers,
            stream=_CoreBodyStream(core_response.stream),
            extensions=core_response.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()
