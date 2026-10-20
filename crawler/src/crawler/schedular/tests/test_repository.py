
import asyncio
import sys

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import update, func, text

from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.models.crawler_frontier import CrawlTarget

from colorama import Fore , Back , init 

init(autoreset=True)

from crawler.schedular.repository import (
    claim_targets,
    recover_expired_leases,
)


async def main():
    async with SessionFactory() as session:

        # All test changes will be rolled back.
        transaction = await session.begin()

        try:
            # --------------------------------------
            # 1. Create an isolated test source
            # --------------------------------------

            unique_id = uuid4().hex

            source = Source(
                slug=f"scheduler-test-{unique_id}",
                name="Scheduler Test",
                kind="website",
                base_url="https://example.com/",
                allowed_hosts=["example.com"],
                crawl_interval_seconds=3600,
                is_enabled=True,
                config={},
            )

            session.add(source)
            await session.flush()

            # --------------------------------------
            # 2. Create two queued targets
            # --------------------------------------

            past = datetime.now(timezone.utc) - timedelta(minutes=1)

            high = CrawlTarget(
                source_id=source.id,
                fetch_url=f"https://example.com/{unique_id}/high",
                normalized_url=f"https://example.com/{unique_id}/high",
                kind="page",
                state="queued",
                priority=10,
                next_fetch_at=past,
            )

            low = CrawlTarget(
                source_id=source.id,
                fetch_url=f"https://example.com/{unique_id}/low",
                normalized_url=f"https://example.com/{unique_id}/low",
                kind="page",
                state="queued",
                priority=5,
                next_fetch_at=past,
            )

            session.add_all([high, low])
            await session.flush()

            print(Fore.CYAN + "Created 2 temporary queued targets.")

            # --------------------------------------
            # TEST 1: Claim highest-priority target
            # --------------------------------------

            # Claim highest-priority target
            first = await claim_targets(
                session,
                limit=1,
                source_id=source.id,
            )

            assert len(first) == 1
            assert first[0].priority == 10

            print(Fore.GREEN + "PASS: Highest-priority target claimed")


            # Claim second target
            second = await claim_targets(
                session,
                limit=1,
                source_id=source.id,
            )

            assert len(second) == 1
            assert second[0].priority == 5

            print(Fore.GREEN + "PASS: Second target claimed")


            # No more eligible targets for this source
            third = await claim_targets(
                session,
                limit=10,
                source_id=source.id,
            )

            assert third == []

            print(Fore.GREEN + "PASS: No more eligible targets")

            # --------------------------------------
            # TEST 4: Active leases stay untouched
            # --------------------------------------

            recovered = await recover_expired_leases(session)

            assert recovered == 0

            print(Fore.GREEN + "PASS: Active leases not recovered")

            # --------------------------------------
            # TEST 5: Simulate an expired lease
            # --------------------------------------

            await session.execute(
                update(CrawlTarget)
                .where(CrawlTarget.id == high.id)
                .values(
                    lease_until=func.now() - text("INTERVAL '1 minute'")
                )
            )

            recovered = await recover_expired_leases(session)

            assert recovered == 1

            await session.refresh(high)
            await session.refresh(low)

            assert high.state == "queued"
            assert high.lease_until is None
            assert low.state == "leased"

            print(Fore.GREEN + "PASS: Expired lease recovered")
            print(Fore.GREEN + "PASS: Non-expired lease preserved")

            # --------------------------------------
            # TEST 6: Reclaim recovered target
            # --------------------------------------

            reclaimed = await claim_targets(
                session,
                limit=1,
                lease_seconds=300,
            )

            assert len(reclaimed) == 1
            assert reclaimed[0].id == high.id
            assert reclaimed[0].state == "leased"

            print(Fore.GREEN + "PASS: Recovered target claimed again")

            # --------------------------------------
            # TEST 7: Reject invalid parameters
            # --------------------------------------

            try:
                await claim_targets(session, limit=0)
                raise AssertionError("Expected ValueError for limit=0")
            except ValueError:
                pass

            try:
                await claim_targets(session, lease_seconds=0)
                raise AssertionError("Expected ValueError for lease_seconds=0")
            except ValueError:
                pass

            print(Fore.GREEN + "PASS: Invalid scheduler parameters rejected")

            print(Fore.YELLOW + "\nALL SCHEDULER TESTS PASSED")

        finally:
            # Remove all temporary database changes
            await transaction.rollback()
            print(Fore.YELLOW +"Test transaction rolled back.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(
            main(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    else:
        asyncio.run(main())
