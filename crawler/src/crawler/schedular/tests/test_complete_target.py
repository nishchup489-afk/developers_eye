
import asyncio
import sys

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from colorama import Fore, Style, just_fix_windows_console

from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.models.crawler_frontier import CrawlTarget

from crawler.schedular.repository import complete_target


just_fix_windows_console()


def log(color: str, status: str, message: str) -> None:
    print(f"{color}[{status}] {message}{Style.RESET_ALL}")


def check(condition: bool, message: str) -> None:
    if condition:
        log(Fore.GREEN, "PASS", message)
    else:
        log(Fore.RED, "FAIL", message)
        raise AssertionError(message)


async def main() -> None:

    log(Fore.CYAN, "START", "Complete Target Integration Tests")

    async with SessionFactory() as session:

        # Explicit transaction: never commit test records
        transaction = await session.begin()

        try:
            # ==========================================
            # SETUP: Create isolated test records
            # ==========================================

            unique_id = uuid4().hex

            source = Source(
                slug=f"completion-test-{unique_id}",
                name="Completion Test Source",
                kind="website",
                base_url="https://example.com/",
                allowed_hosts=["example.com"],
                crawl_interval_seconds=86400,
                is_enabled=True,
                config={},
            )

            session.add(source)
            await session.flush()

            now = datetime.now(timezone.utc)

            active_lease = now + timedelta(minutes=10)
            expired_lease = now - timedelta(minutes=10)

            def make_target(
                suffix: str,
                lease_until: datetime,
            ) -> CrawlTarget:

                url = f"https://example.com/{unique_id}/{suffix}"

                return CrawlTarget(
                    source_id=source.id,
                    fetch_url=url,
                    normalized_url=url,
                    kind="page",
                    state="leased",
                    priority=0,
                    next_fetch_at=now - timedelta(minutes=1),
                    lease_until=lease_until,
                    failure_count=3,
                )

            successful_target = make_target(
                "success",
                active_lease,
            )

            stale_target = make_target(
                "stale",
                active_lease,
            )

            expired_target = make_target(
                "expired",
                expired_lease,
            )

            session.add_all([
                successful_target,
                stale_target,
                expired_target,
            ])

            await session.flush()

            log(Fore.CYAN, "SETUP", "Created 3 temporary leased targets")

            # ==========================================
            # TEST 1: Successful completion
            # ==========================================

            completed = await complete_target(
                session=session,
                target_id=successful_target.id,
                expected_lease_until=active_lease,
                crawl_interval_seconds=86400,
            )

            check(completed is True, "Successful completion returns True")

            await session.refresh(successful_target)

            # ==========================================
            # TEST 2: State changes to queued
            # ==========================================

            check(
                successful_target.state == "queued",
                "State changed: leased -> queued",
            )

            # ==========================================
            # TEST 3: Lease cleared
            # ==========================================

            check(
                successful_target.lease_until is None,
                "Lease cleared after completion",
            )

            # ==========================================
            # TEST 4: Last fetch time recorded
            # ==========================================

            check(
                successful_target.last_fetched_at is not None,
                "last_fetched_at updated",
            )

            # ==========================================
            # TEST 5: Next crawl scheduled correctly
            # ==========================================

            interval = (
                successful_target.next_fetch_at
                - successful_target.last_fetched_at
            ).total_seconds()

            check(
                abs(interval - 86400) < 2,
                "Next crawl scheduled 24 hours after completion",
            )

            # ==========================================
            # TEST 6: Failure counter reset
            # ==========================================

            check(
                successful_target.failure_count == 0,
                "Consecutive failure counter reset to zero",
            )

            # ==========================================
            # TEST 7: Duplicate completion rejected
            # ==========================================

            duplicate = await complete_target(
                session,
                successful_target.id,
                active_lease,
                86400,
            )

            check(
                duplicate is False,
                "Already-completed target cannot complete again",
            )

            # ==========================================
            # TEST 8: Mismatched lease rejected
            # ==========================================

            wrong_lease = active_lease - timedelta(seconds=30)

            stale_result = await complete_target(
                session,
                stale_target.id,
                wrong_lease,
                86400,
            )

            await session.refresh(stale_target)

            check(
                stale_result is False
                and stale_target.state == "leased",
                "Mismatched lease rejected without changing target",
            )

            # ==========================================
            # TEST 9: Expired lease rejected
            # ==========================================

            expired_result = await complete_target(
                session,
                expired_target.id,
                expired_lease,
                86400,
            )

            await session.refresh(expired_target)

            check(
                expired_result is False
                and expired_target.state == "leased",
                "Expired lease cannot complete a target",
            )

            # ==========================================
            # TEST 10: Invalid target ID rejected
            # ==========================================

            try:
                await complete_target(
                    session,
                    0,
                    active_lease,
                    86400,
                )
            except ValueError:
                check(True, "Invalid target ID rejected")
            else:
                check(False, "Invalid target ID was accepted")

            # ==========================================
            # TEST 11: Invalid crawl interval rejected
            # ==========================================

            try:
                await complete_target(
                    session,
                    stale_target.id,
                    active_lease,
                    0,
                )
            except ValueError:
                check(True, "Zero crawl interval rejected")
            else:
                check(False, "Zero crawl interval was accepted")

            # ==========================================
            # TEST 12: Naive datetime rejected
            # ==========================================

            try:
                await complete_target(
                    session,
                    stale_target.id,
                    datetime.now(),  # No timezone
                    86400,
                )
            except ValueError:
                check(True, "Timezone-naive lease timestamp rejected")
            else:
                check(False, "Naive datetime was accepted")

            # ==========================================
            # FINAL REPORT
            # ==========================================

            print()
            log(
                Fore.CYAN,
                "SUCCESS",
                "ALL 12 COMPLETE_TARGET CHECKS PASSED",
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


if __name__ == "__main__":

    if sys.platform == "win32":
        asyncio.run(
            main(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    else:
        asyncio.run(main())
