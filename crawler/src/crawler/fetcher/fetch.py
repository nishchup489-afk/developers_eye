"""Exactly one authorized GET; no redirects, retries, database writes or parsing.

The PolicyCoordinator supplies the approved destination IPs, limits, and user
agent. This module buffers only a bounded, supported textual response body.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence

import httpx

from crawler.policy_and_politeness.redirect_policy import validate_redirect_url

from .client import create_pinned_client
from .config import FetcherConfig
from .errors import FetcherSecurityError, ResponseTooLargeError
from .schemas import OneHopResponse
from .transport import validate_approved_ips


class HTTPXHopFetcher:
    """Concrete implementation of the coordinator's OneHopFetcher Protocol."""

    def __init__(self, config: FetcherConfig | None = None) -> None:
        self.config = config if config is not None else FetcherConfig()

    async def fetch_once(
        self,
        *,
        url: str,
        approved_ips: Sequence[str],
        max_body_bytes: int,
        timeout_seconds: float,
        user_agent: str,
    ) -> OneHopResponse:
        if type(max_body_bytes) is not int or max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be a positive integer")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (float, int))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be a nonempty string")
        if any(ord(c) < 32 or ord(c) == 127 for c in user_agent):
            raise FetcherSecurityError("Unsafe User-Agent characters")

        try:
            canonical_url = validate_redirect_url(url)
            parsed = httpx.URL(canonical_url)
        except (ValueError, TypeError, httpx.InvalidURL) as exc:
            raise FetcherSecurityError("Invalid or unsupported request URL") from exc
        if parsed.scheme not in ("http", "https") or not parsed.host:
            raise FetcherSecurityError("Only absolute HTTP(S) URLs are supported")

        # Re-validate even if the caller is expected to have done so already.
        safe_ips = validate_approved_ips(approved_ips)

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html, application/xhtml+xml, text/plain, application/json, application/xml, text/xml, application/rss+xml, application/atom+xml",
            # Identity keeps compressed content from bypassing raw-size limits.
            # Reject servers that ignore the request and send compressed bytes.
            "Accept-Encoding": "identity",
        }

        try:
            async with asyncio.timeout(float(timeout_seconds)):
                async with create_pinned_client(
                    url=canonical_url,
                    approved_ips=safe_ips,
                    timeout_seconds=float(timeout_seconds),
                ) as client:
                    async with client.stream("GET", canonical_url, headers=headers) as response:
                        response_headers = dict(response.headers)
                        status = response.status_code

                        # Redirects and errors are handled by PolicyCoordinator.
                        # Do not read potentially large error/redirect bodies.
                        if status != 200:
                            return OneHopResponse(status, response_headers)

                        if not self.config.permits_media_type(response.headers.get("content-type")):
                            return OneHopResponse(status, response_headers)

                        encoding = response.headers.get("content-encoding", "identity").strip().casefold()
                        if encoding not in ("", "identity"):
                            raise FetcherSecurityError(
                                f"Unexpected Content-Encoding: {encoding!r}; identity required"
                            )

                        declared_length = response.headers.get("content-length")
                        if declared_length is not None:
                            # HTTP framing should be well-formed. A bad Content-Length
                            # is not an excuse to read an unbounded response.
                            if not declared_length.isascii() or not declared_length.isdecimal():
                                raise FetcherSecurityError("Malformed Content-Length header")
                            if int(declared_length) > max_body_bytes:
                                raise ResponseTooLargeError(
                                    f"Content-Length exceeds {max_body_bytes} bytes"
                                )

                        body_chunks: list[bytes] = []
                        received = 0
                        async for chunk in response.aiter_bytes(chunk_size=self.config.chunk_size):
                            received += len(chunk)
                            if received > max_body_bytes:
                                raise ResponseTooLargeError(
                                    f"Response exceeds {max_body_bytes} bytes"
                                )
                            body_chunks.append(chunk)

                        return OneHopResponse(status, response_headers, b"".join(body_chunks))
        except TimeoutError:
            # Coordinator already interprets TimeoutError as a temporary failure.
            raise
