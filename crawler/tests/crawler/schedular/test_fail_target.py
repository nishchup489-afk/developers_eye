
import asyncio
import sys

from datetime import datetime, timedelta
from uuid import uuid4

from colorama import Fore, Style, just_fix_windows_console
from sqlalchemy import select, func

from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.models.crawler_frontier import CrawlTarget

from crawler.schedular.repository import (
    fail_target,
    calculate_retry_delay,
)


just_fix_windows_console()

passed = 0


# ==========================================
# COLORAMA LOGGING
# ==========================================

def log(color: str, status: str, message: str) -> None:
    print(
        f"{color}[{status}] {message}{Style.RESET_ALL}"
    )


def check(condition: bool, message: str) -> None:
    global passed

    if condition:
        passed += 1
        log(Fore.GREEN, "PASS", message)
    else:
        log(Fore.RED, "FAIL", message)
        raise AssertionError(message)


def check_value_error(callback, message: str) -> None:
    try:
        callback()
    except ValueError:
        check(True, message)
    else:
        check(False, message)


def check_retry_time(
    target: CrawlTarget,
    db_now: datetime,
    expected_seconds: int,
    message: str,
) -> None:
    actual_seconds = (
        target.next_fetch_at - db_now
    ).total_seconds()

    check(
        abs(actual_seconds - expected_seconds) < 2,
        message,
    )


# ==========================================
# MAIN INTEGRATION TEST
# ==========================================

async def main() -> None:
    global passed

    log(
        Fore.CYAN,
        "START",
        "Fail Target Integration Tests",
    )

    async with SessionFactory() as session:
        transaction = await session.begin()

        try:
            # ==========================================
            # SETUP: Temporary test records
            # ==========================================

            unique_id = uuid4().hex

            source = Source(
                slug=f"failure-test-{unique_id}",
                name="Failure Test Source",
                kind="website",
                base_url="https://example.com/",
                allowed_hosts=["example.com"],
                crawl_interval_seconds=86400,
                is_enabled=True,
                config={},
            )

            session.add(source)
            await session.flush()

            # PostgreSQL now() is stable within a transaction.
            # Use the same reference time for retry assertions.
            db_now = await session.scalar(
                select(func.now())
            )

            active_lease = db_now + timedelta(
                minutes=10
            )

            expired_lease = db_now - timedelta(
                minutes=10
            )

            def make_target(
                suffix: str,
                failure_count: int,
                lease_until: datetime,
            ) -> CrawlTarget:

                url = (
                    f"https://example.com/"
                    f"{unique_id}/{suffix}"
                )

                return CrawlTarget(
                    source_id=source.id,
                    fetch_url=url,
                    normalized_url=url,
                    kind="page",
                    state="leased",
                    priority=0,
                    next_fetch_at=db_now - timedelta(
                        minutes=1
                    ),
                    lease_until=lease_until,
                    failure_count=failure_count,
                )

            first_target = make_target(
                "first-failure", 0, active_lease
            )

            third_target = make_target(
                "third-failure", 2, active_lease
            )

            seventh_target = make_target(
                "seventh-failure", 6, active_lease
            )

            capped_target = make_target(
                "twenty-first-failure", 20, active_lease
            )

            stale_target = make_target(
                "stale-lease", 0, active_lease
            )

            expired_target = make_target(
                "expired-lease", 0, expired_lease
            )

            session.add_all([
                first_target,
                third_target,
                seventh_target,
                capped_target,
                stale_target,
                expired_target,
            ])

            await session.flush()

            log(
                Fore.CYAN,
                "SETUP",
                "Created 6 temporary leased targets",
            )

            # ==========================================
            # TEST 1: Retry delay calculations
            # ==========================================

            log(
                Fore.CYAN,
                "SECTION",
                "Testing exponential backoff",
            )

            expected_delays = {
                1: 60,
                2: 120,
                3: 240,
                4: 480,
                5: 960,
                6: 1920,
                7: 3600,
                8: 3600,
                10: 3600,
            }

            for failure_count, expected in (
                expected_delays.items()
            ):
                actual = calculate_retry_delay(
                    failure_count
                )

                check(
                    actual == expected,
                    (
                        f"Failure {failure_count}: "
                        f"delay = {expected}s"
                    ),
                )

            # ==========================================
            # TEST 2: First failure
            # ==========================================

            log(
                Fore.CYAN,
                "SECTION",
                "Testing first failure",
            )

            result = await fail_target(
                session=session,
                target_id=first_target.id,
                expected_lease_until=active_lease,
            )

            check(
                result is True,
                "First failure returns True",
            )

            await session.refresh(first_target)

            check(
                first_target.state == "queued",
                "Failed target changed to queued",
            )

            check(
                first_target.lease_until is None,
                "Lease cleared after failure",
            )

            check(
                first_target.failure_count == 1,
                "Failure counter incremented: 0 -> 1",
            )

            check_retry_time(
                first_target,
                db_now,
                60,
                "First retry scheduled after 60 seconds",
            )

            check(
                first_target.last_fetched_at is None,
                "Last successful fetch timestamp unchanged",
            )

            # ==========================================
            # TEST 3: Third consecutive failure
            # ==========================================

            log(
                Fore.CYAN,
                "SECTION",
                "Testing multiple failures",
            )

            result = await fail_target(
                session,
                third_target.id,
                active_lease,
            )

            await session.refresh(third_target)

            check(
                result is True,
                "Third failure accepted",
            )

            check(
                third_target.failure_count == 3,
                "Failure counter incremented: 2 -> 3",
            )

            check_retry_time(
                third_target,
                db_now,
                240,
                "Third failure retries after 240 seconds",
            )

            # ==========================================
            # TEST 4: Maximum retry delay
            # ==========================================

            result = await fail_target(
                session,
                seventh_target.id,
                active_lease,
            )

            await session.refresh(seventh_target)

            check(
                result is True
                and seventh_target.failure_count == 7,
                "Seventh failure accepted",
            )

            check_retry_time(
                seventh_target,
                db_now,
                3600,
                "Retry delay capped at 3600 seconds",
            )

            # ==========================================
            # TEST 5: Cap remains after many failures
            # ==========================================

            result = await fail_target(
                session,
                capped_target.id,
                active_lease,
            )

            await session.refresh(capped_target)

            check(
                result is True
                and capped_target.failure_count == 21,
                "Failure counter continues past delay cap",
            )

            check_retry_time(
                capped_target,
                db_now,
                3600,
                "Retry delay stays capped after 21 failures",
            )

            # ==========================================
            # TEST 6: Duplicate failure rejected
            # ==========================================

            log(
                Fore.CYAN,
                "SECTION",
                "Testing lease ownership",
            )

            duplicate = await fail_target(
                session,
                first_target.id,
                active_lease,
            )

            await session.refresh(first_target)

            check(
                duplicate is False,
                "Duplicate failure rejected",
            )

            check(
                first_target.failure_count == 1,
                "Duplicate report does not increase count",
            )

            # ==========================================
            # TEST 7: Mismatched lease rejected
            # ==========================================

            wrong_lease = active_lease - timedelta(
                seconds=30
            )

            stale_result = await fail_target(
                session,
                stale_target.id,
                wrong_lease,
            )

            await session.refresh(stale_target)

            check(
                stale_result is False,
                "Mismatched lease rejected",
            )

            check(
                stale_target.state == "leased"
                and stale_target.failure_count == 0,
                "Mismatched lease does not modify target",
            )

            # ==========================================
            # TEST 8: Expired lease rejected
            # ==========================================

            expired_result = await fail_target(
                session,
                expired_target.id,
                expired_lease,
            )

            await session.refresh(expired_target)

            check(
                expired_result is False,
                "Expired lease rejected",
            )

            check(
                expired_target.state == "leased"
                and expired_target.failure_count == 0,
                "Expired lease does not modify target",
            )

            # ==========================================
            # TEST 9: Missing target
            # ==========================================

            missing_result = await fail_target(
                session,
                999999999999,
                active_lease,
            )

            check(
                missing_result is False,
                "Nonexistent target returns False",
            )

            # ==========================================
            # TEST 10: Invalid parameters
            # ==========================================

            log(
                Fore.CYAN,
                "SECTION",
                "Testing parameter validation",
            )

            check_value_error(
                lambda: calculate_retry_delay(0),
                "Zero failure_count rejected",
            )

            check_value_error(
                lambda: calculate_retry_delay(
                    1, base_delay_seconds=0
                ),
                "Zero base delay rejected",
            )

            check_value_error(
                lambda: calculate_retry_delay(
                    1,
                    base_delay_seconds=120,
                    max_delay_seconds=60,
                ),
                "Maximum delay below base rejected",
            )

            async def expect_async_value_error(
                kwargs: dict,
                message: str,
            ) -> None:

                try:
                    await fail_target(
                        session=session,
                        **kwargs,
                    )
                except ValueError:
                    check(True, message)
                else:
                    check(False, message)

            await expect_async_value_error(
                {
                    "target_id": 0,
                    "expected_lease_until": active_lease,
                },
                "Invalid target ID rejected",
            )

            await expect_async_value_error(
                {
                    "target_id": stale_target.id,
                    "expected_lease_until": active_lease,
                    "base_delay_seconds": 0,
                },
                "Invalid base delay rejected",
            )

            await expect_async_value_error(
                {
                    "target_id": stale_target.id,
                    "expected_lease_until": active_lease,
                    "base_delay_seconds": 120,
                    "max_delay_seconds": 60,
                },
                "Maximum delay below base rejected",
            )

            await expect_async_value_error(
                {
                    "target_id": stale_target.id,
                    "expected_lease_until": datetime.now(),
                },
                "Timezone-naive lease rejected",
            )

            # ==========================================
            # FINAL REPORT
            # ==========================================

            print()

            log(
                Fore.CYAN,
                "SUCCESS",
                f"ALL {passed} FAIL_TARGET CHECKS PASSED",
            )

        except Exception as exc:
            log(
                Fore.RED,
                "FAILED",
                f"Integration test failed: {exc}",
            )
            raise

        finally:
            if transaction.is_active:
                await transaction.rollback()

            log(
                Fore.CYAN,
                "CLEANUP",
                "Test transaction rolled back",
            )


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":

    if sys.platform == "win32":
        asyncio.run(
            main(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    else:
        asyncio.run(main())
