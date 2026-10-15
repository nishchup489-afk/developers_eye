"""Secure request orchestration for Developer's Eye.

For each page/redirect: approved host -> safe DNS -> robots -> politeness ->
IP-pinned HTTP GET. Robots retrieval uses the same IP-pinned, host-restricted
network path but does not recursively check robots for /robots.txt.

Single-process in-memory politeness. The caller manages SQLAlchemy transactions
and persists/retries DEFER outcomes in the scheduler. No unchecked redirects,
proxy settings, or arbitrary request headers are accepted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from collections.abc import Sequence
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from crawler.policy_and_politeness.dns_policy import (
    DNSResolutionError,
    UnsafeDestinationError,
    resolve_safe_destination,
    safe_http_transport,
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
    validate_redirect_url,
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


DEFAULT_MAX_BODY_BYTES = 2_000_000
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0


class HostNotAllowedError(ValueError):
    """The source registry does not permit this destination host."""


class ResponseTooLargeError(ValueError):
    """The decoded response body exceeds the configured limit."""


@dataclass(frozen=True, slots=True)
class FetchResult:
    decision: RobotsDecision
    reason: str
    requested_url: str
    final_url: str
    redirect_chain: tuple[str, ...] = ()
    status_code: int | None = None
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    retry_after_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class _HTTPResult:
    status_code: int
    headers: dict[str, str]
    body: bytes


class PolicyCoordinator:
    """Enforce the five policies around each safe, streamed HTTP GET."""

    def __init__(
        self,
        *,
        allowed_hosts: Sequence[str],
        politeness_manager: PolitenessManager | None = None,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        user_agent: str = USER_AGENT,
    ) -> None:
        if (
            isinstance(allowed_hosts, (str, bytes))
            or not allowed_hosts
            or not all(isinstance(host, str) and host for host in allowed_hosts)
        ):
            raise ValueError("allowed_hosts must be a non-empty sequence of hostnames")
        if isinstance(max_body_bytes, bool) or not isinstance(max_body_bytes, int) or max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be a positive integer")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive and finite")
        if not isinstance(user_agent, str) or not user_agent.strip():
            raise ValueError("user_agent must be non-empty")
        # RedirectTracker validates max_redirects, including boolean rejection.
        RedirectTracker("https://example.com/", max_redirects=max_redirects)

        self.allowed_hosts = tuple(allowed_hosts)
        self.politeness = politeness_manager if politeness_manager is not None else PolitenessManager()
        self.max_redirects = max_redirects
        self.max_body_bytes = max_body_bytes
        self.timeout_seconds = float(timeout_seconds)
        self.user_agent = user_agent

    async def _approved_ips(self, url: str) -> list[str]:
        """Do not resolve an unapproved URL's hostname."""
        if not is_allowed_host(url, self.allowed_hosts):
            raise HostNotAllowedError(f"Source registry does not allow {url}")
        host = urlsplit(url).hostname
        if host is None:
            raise HostNotAllowedError("URL has no hostname")
        return await resolve_safe_destination(host)

    async def _get_once(self, url: str, ips: Sequence[str], *, max_bytes: int) -> _HTTPResult:
        """GET exactly one URL over validated IPs; close stream before releasing slot."""
        transport = safe_http_transport(url, ips)
        async with self.politeness.polite_slot(url):
            async with httpx.AsyncClient(
                transport=transport,
                timeout=self.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                headers={"User-Agent": self.user_agent, "Accept": "*/*"},
            ) as client:
                async with client.stream("GET", url) as response:
                    status = response.status_code
                    headers = dict(response.headers)
                    # No body is needed for redirect or backoff decisions.
                    if is_redirect(status) or status in (429, 503):
                        body = b""
                    else:
                        chunks: list[bytes] = []
                        length = 0
                        async for chunk in response.aiter_bytes():
                            length += len(chunk)
                            if length > max_bytes:
                                raise ResponseTooLargeError(
                                    f"Response exceeded {max_bytes} decoded bytes"
                                )
                            chunks.append(chunk)
                        body = b"".join(chunks)
                    # This must happen while holding the politeness slot.
                    await self.politeness.record_response(
                        url, status, response.headers.get("Retry-After")
                    )
                    return _HTTPResult(status, headers, body)

    async def _fetch_robots(self, robots_url: str) -> RobotsFetchResponse:
        """Fetch robots.txt with host, DNS, politeness, redirect and size safety.

        Fetching robots.txt is a special bootstrap operation: checking its own
        robots permissions would recurse forever. Cross-host redirects still
        must pass the original source's allowlist and DNS checks.
        """
        try:
            tracker = RedirectTracker(robots_url, max_redirects=self.max_redirects)
            while True:
                current = tracker.current_url
                ips = await self._approved_ips(current)
                response = await self._get_once(current, ips, max_bytes=MAX_ROBOTS_BYTES)
                if is_redirect(response.status_code):
                    tracker.next_url(response.status_code, response.headers.get("location"))
                    continue
                seconds = parse_retry_after(response.headers.get("retry-after"))
                retry = math.ceil(min(seconds, self.politeness.max_backoff_seconds)) if seconds is not None else None
                return RobotsFetchResponse(
                    status_code=response.status_code,
                    body=response.body.decode("utf-8", errors="replace") if response.status_code == 200 else "",
                    retry_after_seconds=retry,
                )
        except (HostNotAllowedError, UnsafeDestinationError, DNSResolutionError,
                RedirectPolicyError, ResponseTooLargeError, httpx.HTTPError, httpx.InvalidURL, OSError) as exc:
            raise RobotsFetchError("Safe robots.txt retrieval failed") from exc

    async def fetch(self, session: AsyncSession, url: str) -> FetchResult:
        """Fetch one URL with security checks for every hop.

        ALLOW means an HTTP response was safely received, not HTTP 200.
        DENY means a policy rejected it. DEFER means the scheduler should retry.
        Never reuse the final URL/body to make a new unchecked network request.
        """
        requested_url = url
        try:
            tracker = RedirectTracker(url, max_redirects=self.max_redirects)
        except (RedirectPolicyError, TypeError) as exc:
            return FetchResult(RobotsDecision.DENY, f"Invalid URL: {exc}", requested_url, str(url))

        history = [tracker.current_url]

        def result(
            decision: RobotsDecision,
            reason: str,
            *,
            status_code: int | None = None,
            body: bytes = b"",
            headers: dict[str, str] | None = None,
            retry_after_seconds: float | None = None,
        ) -> FetchResult:
            return FetchResult(
                decision=decision,
                reason=reason,
                requested_url=requested_url,
                final_url=tracker.current_url,
                redirect_chain=tuple(history),
                status_code=status_code,
                body=body,
                headers=headers if headers is not None else {},
                retry_after_seconds=retry_after_seconds,
            )

        while True:
            current = tracker.current_url
            try:
                ips = await self._approved_ips(current)
            except (HostNotAllowedError, UnsafeDestinationError) as exc:
                return result(RobotsDecision.DENY, str(exc))
            except (DNSResolutionError, OSError) as exc:
                return result(RobotsDecision.DEFER, f"DNS lookup failed: {exc}",
                              retry_after_seconds=DEFAULT_DEFER_SECONDS)

            try:
                robots = await evaluate_robots_policy(
                    session, current, self._fetch_robots, user_agent=self.user_agent
                )
            except (httpx.HTTPError, OSError) as exc:
                return result(RobotsDecision.DEFER, f"Robots check failed: {exc}",
                              retry_after_seconds=DEFAULT_DEFER_SECONDS)
            if robots.decision != RobotsDecision.ALLOW:
                return result(robots.decision, robots.reason,
                              retry_after_seconds=robots.retry_after_seconds)

            try:
                response = await self._get_once(current, ips, max_bytes=self.max_body_bytes)
            except (UnsafeDestinationError, HostNotAllowedError, ResponseTooLargeError, httpx.InvalidURL) as exc:
                return result(RobotsDecision.DENY, str(exc))
            except (httpx.HTTPError, OSError) as exc:
                return result(RobotsDecision.DEFER, f"HTTP fetch failed: {exc}",
                              retry_after_seconds=DEFAULT_DEFER_SECONDS)

            if is_redirect(response.status_code):
                try:
                    target = tracker.next_url(
                        response.status_code, response.headers.get("location")
                    )
                except RedirectPolicyError as exc:
                    return result(RobotsDecision.DENY, f"Redirect rejected: {exc}",
                                  status_code=response.status_code)
                history.append(target)
                continue

            if response.status_code in (429, 503):
                delay = parse_retry_after(response.headers.get("retry-after"))
                if delay is None:
                    delay = self.politeness.default_backoff_seconds
                return result(RobotsDecision.DEFER, f"HTTP {response.status_code}: retry later",
                              status_code=response.status_code,
                              headers=response.headers,
                              retry_after_seconds=min(delay, self.politeness.max_backoff_seconds))

            if 500 <= response.status_code <= 599:
                return result(RobotsDecision.DEFER, f"HTTP {response.status_code}: server failure",
                              status_code=response.status_code,
                              retry_after_seconds=DEFAULT_DEFER_SECONDS)

            return result(RobotsDecision.ALLOW, f"Fetched HTTP {response.status_code}",
                          status_code=response.status_code,
                          headers=response.headers, body=response.body)
