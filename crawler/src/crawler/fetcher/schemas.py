"""Shared one-request contract between PolicyCoordinator and HTTPXHopFetcher.

FetchResult is intentionally NOT defined here: the policy coordinator owns the
final, multi-hop result. This contract represents exactly one HTTP GET.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OneHopResponse:
    """Status, headers, and a fully consumed (or deliberately skipped) body."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes = b""


class OneHopFetcher(Protocol):
    """Execute one GET with IP-pinned transport and no automatic redirects."""

    async def fetch_once(
        self,
        *,
        url: str,
        approved_ips: Sequence[str],
        max_body_bytes: int,
        timeout_seconds: float,
        user_agent: str,
    ) -> OneHopResponse: ...

"""
If you want to work with the Policy Coordinator, 
you must implement fetch_once() with these parameters 
and return a OneHopResponse.
"""