"""Create an HTTPX client scoped to one approved request and one IP set."""

from __future__ import annotations

import httpx

from .transport import PinnedAsyncTransport


def create_pinned_client(
    *, url: str, approved_ips: tuple[str, ...], timeout_seconds: float
) -> httpx.AsyncClient:
    """Caller must use `async with` to close the client and transport.

    A request-scoped pool prevents later fetches from reusing a socket that is
    no longer among their approved_ips. Overall deadline is enforced in fetch.py.
    """
    transport = PinnedAsyncTransport(
        expected_url=httpx.URL(url),
        approved_ips=approved_ips,
    )
    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,
        trust_env=False,
        http2=False,
        timeout=httpx.Timeout(timeout_seconds),
        max_redirects=0,
    )
