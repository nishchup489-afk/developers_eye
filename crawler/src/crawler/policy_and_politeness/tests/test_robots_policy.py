"""Integration tests for crawler.robot.robots_policy.

Run from the repository root (with backend and crawler importable):
    python -m crawler.robot.tests.test_robots_policy

Uses PostgreSQL and mocked robots retrieval. All database changes are rolled back.
Do not run against production.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from colorama import Fore, Style, just_fix_windows_console
from sqlalchemy import func, select, update

from backend.db.session import SessionFactory
from backend.models.robot_cache import RobotsCache
from crawler.policy_and_politeness.robots_policy import (
    DEFAULT_DEFER_SECONDS,
    MAX_ROBOTS_BYTES,
    RobotsDecision,
    RobotsFetchError,
    RobotsFetchResponse,
    evaluate_robots_policy,
    get_cached_robots,
    get_robots_origin,
    get_robots_url,
    is_crawl_allowed,
    parse_robots,
    save_robots_cache,
)


just_fix_windows_console()
passed = 0


# ----------------------------------------------------------
# Console helpers
# ----------------------------------------------------------

def log(color: str, label: str, message: str) -> None:
    print(f"{color}[{label}] {message}{Style.RESET_ALL}")


def check(condition: bool, message: str) -> None:
    global passed
    if not condition:
        log(Fore.RED, "FAIL", message)
        raise AssertionError(message)
    passed += 1
    log(Fore.GREEN, "PASS", message)


def check_raises(error_type: type[Exception], callback, message: str) -> None:
    try:
        callback()
    except error_type:
        check(True, message)
    else:
        check(False, message)


class FakeFetcher:
    """Returns a chosen response; never opens any network connection."""

    def __init__(self, result: RobotsFetchResponse | Exception):
        self.result = result
        self.calls: list[str] = []

    async def __call__(self, url: str) -> RobotsFetchResponse:
        self.calls.append(url)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


RULES = """User-agent: DevelopersEyeBot
Disallow: /private/
Allow: /docs/

User-agent: *
Disallow: /everyone-blocked/
"""


async def main() -> None:
    global passed
    passed = 0
    run_id = uuid4().hex

    def site(name: str) -> str:
        # Unique, non-real host. FakeFetcher means no outbound requests.
        return f"https://{name}-{run_id}.example"

    log(Fore.CYAN, "START", "Robots Policy Tests")

    # ------------------------------------------------------
    # 1. Pure Python tests - no database access
    # ------------------------------------------------------
    log(Fore.CYAN, "SECTION", "Origin and robots URL construction")

    check(
        get_robots_origin("HTTPS://EXAMPLE.COM:443/docs?q=1#part")
        == "https://example.com",
        "Origin strips path, query, fragment and default port",
    )
    check(
        get_robots_url("https://example.com/article?q=1#part")
        == "https://example.com/robots.txt",
        "Robots URL uses site root",
    )
    check(
        get_robots_url("http://example.com/docs")
        == "http://example.com/robots.txt",
        "HTTP origin is preserved",
    )
    check(
        get_robots_url("https://example.com:8443/docs")
        == "https://example.com:8443/robots.txt",
        "Non-default port is preserved",
    )
    check_raises(
        ValueError,
        lambda: get_robots_url("file:///etc/passwd"),
        "Non-HTTP URL rejected",
    )

    log(Fore.CYAN, "SECTION", "Robots parsing and path permissions")

    parser = parse_robots(RULES)
    check(
        parser.can_fetch("DevelopersEyeBot", "https://example.com/docs/python"),
        "Parser allows approved /docs/ path",
    )
    check(
        not is_crawl_allowed(RULES, "https://example.com/private/secret"),
        "Parser denies /private/ for DevelopersEyeBot",
    )
    check(
        not is_crawl_allowed(
            RULES, "https://example.com/everyone-blocked/test", "OtherBot"
        ),
        "Wildcard user-agent rules apply to other bots",
    )
    check(
        is_crawl_allowed("", "https://example.com/public"),
        "Empty but successfully fetched robots file allows public path",
    )
    check_raises(
        TypeError,
        lambda: parse_robots(None),  # type: ignore[arg-type]
        "Non-text robots content rejected",
    )

    # ------------------------------------------------------
    # 2. Real PostgreSQL tests, no commits
    # ------------------------------------------------------
    async with SessionFactory() as session:
        transaction = await session.begin()
        try:
            origin = site("db-cache")

            log(Fore.CYAN, "SECTION", "PostgreSQL robots_cache operations")

            check(
                await get_cached_robots(session, origin) is None,
                "Missing cache returns None",
            )

            await save_robots_cache(
                session, origin, http_status=200, raw_content=RULES,
                ttl_seconds=3600,
            )
            cached = await get_cached_robots(session, origin)
            check(cached is not None, "New cache row is readable")
            check(
                cached is not None
                and cached.http_status == 200
                and cached.raw_content == RULES,
                "Cache stores HTTP status and raw robots text",
            )
            check(
                cached is not None
                and cached.fetched_at.tzinfo is not None
                and cached.expires_at > cached.fetched_at,
                "Cache has timezone-aware timestamps and positive TTL",
            )

            await save_robots_cache(
                session, origin, http_status=404, raw_content=None,
                ttl_seconds=600,
            )
            refreshed = await get_cached_robots(session, origin)
            check(
                refreshed is not None
                and refreshed.http_status == 404
                and refreshed.raw_content is None,
                "Upsert replaces previous cache values",
            )
            row_count = await session.scalar(
                select(func.count()).select_from(RobotsCache).where(
                    RobotsCache.origin == origin
                )
            )
            check(row_count == 1, "Upsert does not create duplicate origin rows")

            await session.execute(
                update(RobotsCache)
                .where(RobotsCache.origin == origin)
                .values(
                    fetched_at=datetime.now(timezone.utc) - timedelta(hours=2),
                    expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
                )
            )
            check(
                await get_cached_robots(session, origin) is None,
                "Expired cache is treated as a miss",
            )

            # --------------------------------------------------
            # 3. Coordinator: cache miss -> fetch -> cache hit
            # --------------------------------------------------
            log(Fore.CYAN, "SECTION", "Coordinator ALLOW / DENY and cache reuse")

            origin = site("coordinator")
            first_fetch = FakeFetcher(RobotsFetchResponse(200, RULES))
            allow_result = await evaluate_robots_policy(
                session, f"{origin}/docs/python", first_fetch,
            )
            check(
                allow_result.decision == RobotsDecision.ALLOW,
                "HTTP 200 + permitted path returns ALLOW",
            )
            check(
                first_fetch.calls == [f"{origin}/robots.txt"],
                "Only the origin's robots.txt URL is requested",
            )

            # Deliberately fail if it gets called: fresh cache must avoid fetch.
            no_network = FakeFetcher(RobotsFetchError("should not fetch"))
            deny_result = await evaluate_robots_policy(
                session, f"{origin}/private/credentials", no_network,
            )
            check(
                deny_result.decision == RobotsDecision.DENY,
                "Cached robots rules correctly return DENY",
            )
            check(
                no_network.calls == [],
                "Fresh cache avoids another network request",
            )

            # --------------------------------------------------
            # 4. Different HTTP outcomes
            # --------------------------------------------------
            log(Fore.CYAN, "SECTION", "HTTP status and network failure decisions")

            missing_origin = site("missing-robots")
            missing_fetch = FakeFetcher(RobotsFetchResponse(404))
            missing_result = await evaluate_robots_policy(
                session, f"{missing_origin}/docs", missing_fetch,
            )
            check(
                missing_result.decision == RobotsDecision.ALLOW,
                "HTTP 404 means no robots restrictions",
            )
            check(
                await get_cached_robots(session, missing_origin) is not None,
                "HTTP 404 result is cached",
            )
            missing_fetch_again = FakeFetcher(RobotsFetchError("not called"))
            await evaluate_robots_policy(
                session, f"{missing_origin}/another-page", missing_fetch_again,
            )
            check(
                missing_fetch_again.calls == [],
                "Cached HTTP 404 avoids repeated requests",
            )

            forbidden_origin = site("forbidden-robots")
            forbidden_result = await evaluate_robots_policy(
                session, f"{forbidden_origin}/docs",
                FakeFetcher(RobotsFetchResponse(403)),
            )
            check(
                forbidden_result.decision == RobotsDecision.DENY,
                "HTTP 403 returns conservative DENY",
            )

            temporarily_unavailable = site("server-error")
            server_result = await evaluate_robots_policy(
                session, f"{temporarily_unavailable}/docs",
                FakeFetcher(RobotsFetchResponse(503)),
            )
            check(
                server_result.decision == RobotsDecision.DEFER
                and server_result.retry_after_seconds == DEFAULT_DEFER_SECONDS,
                "HTTP 503 returns DEFER with default delay",
            )
            check(
                await get_cached_robots(session, temporarily_unavailable) is None,
                "HTTP 503 is not cached as an allow/deny policy",
            )

            rate_limited = site("rate-limited")
            rate_result = await evaluate_robots_policy(
                session, f"{rate_limited}/docs",
                FakeFetcher(RobotsFetchResponse(429, retry_after_seconds=900)),
            )
            check(
                rate_result.decision == RobotsDecision.DEFER
                and rate_result.retry_after_seconds == 900,
                "HTTP 429 respects supplied retry delay",
            )

            failure_result = await evaluate_robots_policy(
                session, f"{site('dns-failure')}/docs",
                FakeFetcher(RobotsFetchError("DNS timeout")),
            )
            check(
                failure_result.decision == RobotsDecision.DEFER,
                "Injected fetch/network failure returns DEFER",
            )

            redirect_result = await evaluate_robots_policy(
                session, f"{site('redirect')}/docs",
                FakeFetcher(RobotsFetchResponse(302)),
            )
            check(
                redirect_result.decision == RobotsDecision.DEFER,
                "Unhandled redirect returns DEFER (not automatically followed)",
            )

            too_big_origin = site("oversized")
            too_big_result = await evaluate_robots_policy(
                session, f"{too_big_origin}/docs",
                FakeFetcher(RobotsFetchResponse(200, "x" * (MAX_ROBOTS_BYTES + 1))),
            )
            check(
                too_big_result.decision == RobotsDecision.DEFER,
                "Oversized robots response returns DEFER",
            )
            check(
                await get_cached_robots(session, too_big_origin) is None,
                "Oversized robots response is not cached",
            )

            invalid_body_result = await evaluate_robots_policy(
                session, f"{site('invalid-body')}/docs",
                FakeFetcher(RobotsFetchResponse(200, None)),  # type: ignore[arg-type]
            )
            check(
                invalid_body_result.decision == RobotsDecision.DEFER,
                "Non-text response body returns DEFER",
            )

            # --------------------------------------------------
            # 5. Validation and errors
            # --------------------------------------------------
            log(Fore.CYAN, "SECTION", "Validation")

            check_raises(
                ValueError,
                lambda: get_robots_url("javascript:alert(1)"),
                "Unsafe URL scheme rejected",
            )
            check_raises(
                ValueError,
                lambda: is_crawl_allowed(RULES, "https://example.com", ""),
                "Empty user agent rejected",
            )

            try:
                await save_robots_cache(session, site("bad-ttl"), 200, RULES, 0)
            except ValueError:
                check(True, "Non-positive cache TTL rejected")
            else:
                check(False, "Non-positive cache TTL was accepted")

            try:
                await evaluate_robots_policy(
                    session, f"{site('bad-config')}/docs",
                    FakeFetcher(RobotsFetchResponse(200, RULES)),
                    cache_ttl_seconds=0,
                )
            except ValueError:
                check(True, "Invalid policy cache TTL rejected")
            else:
                check(False, "Invalid policy cache TTL was accepted")

            print()
            log(Fore.CYAN, "SUCCESS", f"ALL {passed} ROBOTS POLICY CHECKS PASSED")

        except Exception as exc:
            log(Fore.RED, "FAILED", f"Test failed: {exc}")
            raise

        finally:
            if transaction.is_active:
                await transaction.rollback()
            log(Fore.CYAN, "CLEANUP", "Test transaction rolled back")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main())
