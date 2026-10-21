"""
Developers Eye - robots.txt policy.

This module does not open network connections itself. Supply a safe fetcher
whose HTTP transport enforces validated IP connections, approved hosts,
redirect safety, timeouts, and response-size limits.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit
from crawler.policy_and_politeness.robots_rules import RobotsRules, parse_rules

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.robot_cache import RobotsCache
from crawler.frontier.urls import normalize_url
from crawler.config import DEFAULT_USER_AGENT


USER_AGENT = DEFAULT_USER_AGENT
DEFAULT_CACHE_TTL_SECONDS = 86_400
MISSING_CACHE_TTL_SECONDS = 3_600
DEFAULT_DEFER_SECONDS = 300
MAX_ROBOTS_BYTES = 512_000


class RobotsDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class RobotsPolicyResult:
    decision: RobotsDecision
    reason: str
    origin: str
    retry_after_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class RobotsFetchResponse:
    status_code: int
    body: str = ""
    retry_after_seconds: int | None = None


class RobotsFetchError(Exception):
    """Raised by the injected safe fetcher for network failures."""


# The fetcher MUST use a safe HTTP transport, not unchecked httpx.get().
RobotsFetcher = Callable[[str], Awaitable[RobotsFetchResponse]]


def get_robots_origin(url: str) -> str:
    """Return the normalized origin (scheme + authority) for an HTTP(S) URL."""
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def get_robots_url(url: str) -> str:
    """Return the /robots.txt URL for the same normalized origin."""
    origin = get_robots_origin(url)
    return f"{origin}/robots.txt"


def parse_robots(raw_content: str) -> RobotsRules:
    """Parse robots.txt text without fetching it."""
    if not isinstance(raw_content, str):
        raise TypeError("raw_content must be text")

    return parse_rules(raw_content)


def is_crawl_allowed(
    raw_content: str,
    url: str,
    user_agent: str = USER_AGENT,
) -> bool:
    """Evaluate a URL against successfully retrieved robots.txt text."""
    if not user_agent or not isinstance(user_agent, str):
        raise ValueError("user_agent must be a non-empty string")

    normalized_url = normalize_url(url)
    parser = parse_robots(raw_content)
    return parser.can_fetch(user_agent, normalized_url)


async def get_cached_robots(
    session: AsyncSession,
    origin: str,
) -> RobotsCache | None:
    """Return an unexpired PostgreSQL robots_cache row, or None."""
    stmt = (
        select(RobotsCache)
        .where(
            RobotsCache.origin == origin,
            RobotsCache.expires_at > datetime.now(timezone.utc),
        )
        .execution_options(populate_existing=True)
    )
    return await session.scalar(stmt)


async def save_robots_cache(
    session: AsyncSession,
    origin: str,
    http_status: int,
    raw_content: str | None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> None:
    """Upsert a robots.txt cache entry. The caller commits the transaction."""
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    if not (100 <= http_status <= 599):
        raise ValueError("http_status must be a valid HTTP status code")

    now = datetime.now(timezone.utc)
    values = {
        "origin": origin,
        "raw_content": raw_content,
        "http_status": http_status,
        "fetched_at": now,
        "expires_at": now + timedelta(seconds=ttl_seconds),
    }

    stmt = pg_insert(RobotsCache).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RobotsCache.origin],
        set_={
            "raw_content": stmt.excluded.raw_content,
            "http_status": stmt.excluded.http_status,
            "fetched_at": stmt.excluded.fetched_at,
            "expires_at": stmt.excluded.expires_at,
        },
    )
    await session.execute(stmt)


def _decision_for_status(
    *,
    url: str,
    origin: str,
    status: int,
    content: str | None,
    user_agent: str,
) -> RobotsPolicyResult:
    """Apply explicit MVP behavior to a cached or newly fetched response."""
    if status == 200:
        permitted = is_crawl_allowed(content or "", url, user_agent)
        return RobotsPolicyResult(
            RobotsDecision.ALLOW if permitted else RobotsDecision.DENY,
            "Robots rules permit URL" if permitted else "Robots rules disallow URL",
            origin,
        )

    if status in (401, 403):
        # Deliberately stricter than RFC 9309's general 4xx guidance.
        return RobotsPolicyResult(
            RobotsDecision.DENY,
            "Robots endpoint denied access (conservative policy)",
            origin,
        )

    if status in (408, 429) or 500 <= status <= 599:
        return RobotsPolicyResult(
            RobotsDecision.DEFER,
            "Robots endpoint temporarily unavailable",
            origin,
            DEFAULT_DEFER_SECONDS,
        )

    if 400 <= status <= 499 or status == 204:
        # RFC 9309: robots.txt unavailable (4xx) -> no robots restrictions.
        return RobotsPolicyResult(
            RobotsDecision.ALLOW,
            "No applicable robots.txt restrictions",
            origin,
        )

    # Unhandled 2xx, 3xx (including redirects), and other responses fail closed.
    return RobotsPolicyResult(
        RobotsDecision.DEFER,
        f"Unhandled robots response: HTTP {status}",
        origin,
        DEFAULT_DEFER_SECONDS,
    )


async def evaluate_robots_policy(
    session: AsyncSession,
    url: str,
    fetcher: RobotsFetcher,
    *,
    user_agent: str = USER_AGENT,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> RobotsPolicyResult:
    """
    Decide ALLOW / DENY / DEFER for a page.

    Preconditions:
    - The caller has checked the URL and source host allowlist.
    - The injected fetcher enforces safe DNS/IP connections and redirects.
    - The caller manages commit/rollback for this AsyncSession.

    No network request is made on a fresh cache hit.
    """
    if cache_ttl_seconds <= 0:
        raise ValueError("cache_ttl_seconds must be positive")
    if not isinstance(user_agent, str) or not user_agent:
        raise ValueError("user_agent must be non-empty")

    origin = get_robots_origin(url)
    cached = await get_cached_robots(session, origin)
    if cached is not None and cached.http_status is not None:
        return _decision_for_status(
            url=url,
            origin=origin,
            status=cached.http_status,
            content=cached.raw_content,
            user_agent=user_agent,
        )

    robots_url = f"{origin}/robots.txt"

    try:
        response = await fetcher(robots_url)
    except RobotsFetchError:
        return RobotsPolicyResult(
            RobotsDecision.DEFER,
            "Robots retrieval failed; retry later",
            origin,
            DEFAULT_DEFER_SECONDS,
        )

    status = response.status_code

    if status == 200:
        if not isinstance(response.body, str):
            return RobotsPolicyResult(
                RobotsDecision.DEFER,
                "Invalid robots.txt response body",
                origin,
                DEFAULT_DEFER_SECONDS,
            )
        if len(response.body.encode("utf-8")) > MAX_ROBOTS_BYTES:
            return RobotsPolicyResult(
                RobotsDecision.DEFER,
                "robots.txt exceeds permitted size",
                origin,
                DEFAULT_DEFER_SECONDS,
            )
        await save_robots_cache(
            session, origin, status, response.body, cache_ttl_seconds
        )

    elif status in (401, 403, 404, 410, 204) or (
        400 <= status <= 499 and status not in (408, 429)
    ):
        await save_robots_cache(
            session, origin, status, None, MISSING_CACHE_TTL_SECONDS
        )

    decision = _decision_for_status(
        url=url,
        origin=origin,
        status=status,
        content=response.body if status == 200 else None,
        user_agent=user_agent,
    )

    if decision.decision == RobotsDecision.DEFER:
        retry_after = response.retry_after_seconds
        if retry_after is not None and retry_after > 0:
            return RobotsPolicyResult(
                decision.decision,
                decision.reason,
                origin,
                retry_after,
            )

    return decision
