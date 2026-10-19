"""Coordinate security and access policies for Developer's Eye.

The coordinator never opens sockets or constructs HTTP clients. A caller
supplies a ONE-REQUEST fetcher whose implementation MUST:

- connect ONLY to the numeric ``approved_ips`` given for that request;
- retain URL hostname for TLS SNI/certificate verification and HTTP Host;
- disable automatic redirects, proxies and environment proxy settings;
- enforce the passed timeout and decoded-body limit while streaming;
- consume or close the response before returning or raising;
- make exactly one GET request (no implicit retry or second DNS lookup).

The worker obtains a URL from the frontier, calls ``fetch()``, then handles
ALLOW/DENY/DEFER. The worker and scheduler manage leases and retries.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from crawler.policy_and_politeness.dns_policy import (
    DNSResolutionError,
    UnsafeDestinationError,
    resolve_safe_destination,
)
from crawler.policy_and_politeness.host_policy import is_allowed_host
from crawler.policy_and_politeness.politeness_policy import (
    PolitenessManager,
    parse_retry_after,
)
from crawler.policy_and_politeness.redirect_policy import (
    DEFAULT_MAX_REDIRECTS,
    RedirectPolicyError,
    RedirectTracker,
    is_redirect,
)
from crawler.policy_and_politeness.robots_policy import (
    DEFAULT_DEFER_SECONDS,
    MAX_ROBOTS_BYTES,
    RobotsDecision,
    RobotsFetchError,
    RobotsFetchResponse,
    USER_AGENT,
    evaluate_robots_policy,
)
from crawler.fetcher.schemas import OneHopFetcher, OneHopResponse

DEFAULT_MAX_BODY_BYTES = 2_000_000
DEFAULT_TIMEOUT_SECONDS = 15.0


class HostNotAllowedError(ValueError):
    """Host is not on the approved source allowlist."""


class ResponseTooLargeError(ValueError):
    """Fetcher rejected a response that exceeded the body-size limit."""


class FetcherSecurityError(ValueError):
    """Fetcher rejected an unsafe transport configuration or destination."""




@dataclass(frozen=True, slots=True)
class FetchResult:
    decision: RobotsDecision
    reason: str
    requested_url: str
    final_url: str
    redirect_chain: tuple[str, ...] = ()
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    retry_after_seconds: float | None = None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Headers are case-insensitive even with a plain dict test double."""
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            return value
    return None


class PolicyCoordinator:
    """Check every URL/redirect hop, then delegate GET I/O to a safe fetcher."""

    def __init__(
        self,
        *,
        allowed_hosts: Sequence[str],
        fetcher: OneHopFetcher,
        politeness_manager: PolitenessManager | None = None,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = USER_AGENT,
    ) -> None:
        if (
            isinstance(allowed_hosts, (str, bytes))
            or not allowed_hosts
            or not all(isinstance(h, str) and bool(h.strip()) for h in allowed_hosts)
        ):
            raise ValueError("allowed_hosts must be a non-empty sequence of hostnames")
        if not callable(getattr(fetcher, "fetch_once", None)):
            raise TypeError("fetcher must expose an async fetch_once(...) method")
        if type(max_body_bytes) is not int or max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be a positive integer")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive and finite")
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be a non-empty string")
        if type(max_redirects) is not int or max_redirects < 0:
            raise ValueError("max_redirects must be a non-negative integer")

        self.allowed_hosts = tuple(allowed_hosts)
        self.fetcher = fetcher
        self.politeness = politeness_manager if politeness_manager is not None else PolitenessManager()
        self.max_redirects = max_redirects
        self.max_body_bytes = max_body_bytes
        self.timeout_seconds = float(timeout_seconds)
        self.user_agent = user_agent

    async def _approved_ips(self, url: str) -> list[str]:
        """Host allowlist MUST run before DNS resolution."""
        if not is_allowed_host(url, self.allowed_hosts):
            raise HostNotAllowedError(f"Host not allowed: {url}")
        host = urlsplit(url).hostname
        if host is None:
            raise HostNotAllowedError("URL has no hostname")
        return await resolve_safe_destination(host)

    async def _request_once(
        self, url: str, approved_ips: Sequence[str], *, max_bytes: int
    ) -> OneHopResponse:
        """Reserve a polite slot around exactly one injected network request."""
        async with self.politeness.polite_slot(url):
            response = await self.fetcher.fetch_once(
                url=url,
                approved_ips=tuple(approved_ips),
                max_body_bytes=max_bytes,
                timeout_seconds=self.timeout_seconds,
                user_agent=self.user_agent,
            )
            # Defense in depth; the fetcher MUST enforce this *while streaming*.
            if len(response.body) > max_bytes:
                raise ResponseTooLargeError(f"Response exceeded {max_bytes} bytes")
            await self.politeness.record_response(
                url,
                response.status_code,
                _header(response.headers, "Retry-After"),
            )
            return response

    async def _fetch_robots(self, robots_url: str) -> RobotsFetchResponse:
        """Bootstrap robots.txt without recursively checking robots.txt itself.

        Any robots redirect still rechecks host, DNS and politeness. Failures
        translate to RobotsFetchError so robots policy can defer the page.
        """
        try:
            tracker = RedirectTracker(robots_url, max_redirects=self.max_redirects)
            while True:
                current = tracker.current_url
                ips = await self._approved_ips(current)
                response = await self._request_once(current, ips, max_bytes=MAX_ROBOTS_BYTES)
                if is_redirect(response.status_code):
                    tracker.next_url(response.status_code, _header(response.headers, "Location"))
                    continue

                wait = parse_retry_after(_header(response.headers, "Retry-After"))
                retry_after = (
                    math.ceil(min(wait, self.politeness.max_backoff_seconds))
                    if wait is not None else None
                )
                return RobotsFetchResponse(
                    status_code=response.status_code,
                    body=response.body.decode("utf-8", errors="replace")
                    if response.status_code == 200 else "",
                    retry_after_seconds=retry_after,
                )
        except (
            HostNotAllowedError,
            UnsafeDestinationError,
            DNSResolutionError,
            RedirectPolicyError,
            ResponseTooLargeError,
            FetcherSecurityError,
            httpx.HTTPError,
            OSError,
            TimeoutError,
        ) as exc:
            raise RobotsFetchError("Safe robots.txt retrieval failed") from exc

    async def fetch(self, session: AsyncSession, url: str) -> FetchResult:
        """Run policies for one frontier URL, following only checked redirects.

        ALLOW means a response was retrieved, not necessarily HTTP 200.
        DENY is a security/policy rejection. DEFER is a temporary condition.
        Do not swallow asyncio.CancelledError or unexpected programming errors.
        """
        requested_url = url
        try:
            tracker = RedirectTracker(url, max_redirects=self.max_redirects)
        except (RedirectPolicyError, TypeError) as exc:
            return FetchResult(
                RobotsDecision.DENY,
                f"Invalid URL: {exc}",
                str(requested_url),
                str(requested_url),
            )

        history = [tracker.current_url]

        def result(
            decision: RobotsDecision,
            reason: str,
            *,
            response: OneHopResponse | None = None,
            retry_after_seconds: float | None = None,
        ) -> FetchResult:
            return FetchResult(
                decision=decision,
                reason=reason,
                requested_url=requested_url,
                final_url=tracker.current_url,
                redirect_chain=tuple(history),
                status_code=response.status_code if response else None,
                headers=dict(response.headers) if response else {},
                body=response.body if response and decision == RobotsDecision.ALLOW else b"",
                retry_after_seconds=retry_after_seconds,
            )

        while True:
            current = tracker.current_url

            try:
                ips = await self._approved_ips(current)
            except (HostNotAllowedError, UnsafeDestinationError) as exc:
                return result(RobotsDecision.DENY, str(exc))
            except (DNSResolutionError, OSError, TimeoutError) as exc:
                return result(
                    RobotsDecision.DEFER,
                    f"DNS resolution failed: {exc}",
                    retry_after_seconds=DEFAULT_DEFER_SECONDS,
                )

            try:
                robots = await evaluate_robots_policy(
                    session,
                    current,
                    self._fetch_robots,
                    user_agent=self.user_agent,
                )
            except (httpx.HTTPError, OSError, TimeoutError) as exc:
                return result(
                    RobotsDecision.DEFER,
                    f"Robots check failed: {exc}",
                    retry_after_seconds=DEFAULT_DEFER_SECONDS,
                )
            if robots.decision != RobotsDecision.ALLOW:
                return result(
                    robots.decision,
                    robots.reason,
                    retry_after_seconds=robots.retry_after_seconds,
                )

            try:
                response = await self._request_once(current, ips, max_bytes=self.max_body_bytes)
            except (ResponseTooLargeError, FetcherSecurityError, UnsafeDestinationError, httpx.InvalidURL) as exc:
                return result(RobotsDecision.DENY, str(exc))
            except (httpx.HTTPError, OSError, TimeoutError) as exc:
                return result(
                    RobotsDecision.DEFER,
                    f"HTTP fetch failed: {exc}",
                    retry_after_seconds=DEFAULT_DEFER_SECONDS,
                )

            if is_redirect(response.status_code):
                try:
                    target = tracker.next_url(
                        response.status_code,
                        _header(response.headers, "Location"),
                    )
                except RedirectPolicyError as exc:
                    return result(
                        RobotsDecision.DENY,
                        f"Redirect rejected: {exc}",
                        response=response,
                    )
                history.append(target)
                continue

            if response.status_code in (429, 503):
                wait = parse_retry_after(_header(response.headers, "Retry-After"))
                if wait is None:
                    wait = self.politeness.default_backoff_seconds
                return result(
                    RobotsDecision.DEFER,
                    f"HTTP {response.status_code}: retry later",
                    response=response,
                    retry_after_seconds=min(wait, self.politeness.max_backoff_seconds),
                )

            if 500 <= response.status_code <= 599:
                return result(
                    RobotsDecision.DEFER,
                    f"HTTP {response.status_code}: server error",
                    response=response,
                    retry_after_seconds=DEFAULT_DEFER_SECONDS,
                )

            return result(
                RobotsDecision.ALLOW,
                f"Fetched HTTP {response.status_code}",
                response=response,
            )
