
import asyncio
import sys

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from colorama import Fore, Style, just_fix_windows_console
from sqlalchemy import func, select, update

from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.models.crawler_frontier import CrawlTarget

from crawler.schedular.repository import claim_targets


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

    log(Fore.CYAN, "START", "Round-robin BFS claim tests")

    async with SessionFactory() as session:

        # Explicit transaction: never commit test records
        transaction = await session.begin()

        try:
            unique_id = uuid4().hex
            past = datetime.now(timezone.utc) - timedelta(minutes=1)
            future = datetime.now(timezone.utc) + timedelta(hours=1)

            # claim_targets() picks sources across the whole table, so other
            # sources in the dev database would interleave with ours. Disable
            # them inside this transaction; the rollback restores them.
            await session.execute(
                update(Source)
                .where(Source.slug.not_like(f"rr-test-{unique_id}-%"))
                .values(is_enabled=False)
            )

            async def make_source(
                label: str,
                *,
                last_claimed_at: datetime | None = None,
                is_enabled: bool = True,
            ) -> Source:
                source = Source(
                    slug=f"rr-test-{unique_id}-{label}",
                    name=f"Round Robin Test {label}",
                    kind="website",
                    base_url="https://example.com/",
                    allowed_hosts=["example.com"],
                    crawl_interval_seconds=3600,
                    is_enabled=is_enabled,
                    config={},
                    last_claimed_at=last_claimed_at,
                )
                session.add(source)
                await session.flush()
                return source

            async def make_target(
                source: Source,
                name: str,
                *,
                priority: int = 50,
                depth: int = 0,
                next_fetch_at: datetime = past,
            ) -> CrawlTarget:
                url = f"https://example.com/{unique_id}/{source.id}/{name}"
                target = CrawlTarget(
                    source_id=source.id,
                    fetch_url=url,
                    normalized_url=url,
                    kind="page",
                    state="queued",
                    priority=priority,
                    depth=depth,
                    next_fetch_at=next_fetch_at,
                )
                session.add(target)
                await session.flush()
                return target

            # ==========================================
            # TEST 1: One call rotates across sources
            # ==========================================
            # A has 3 due targets, B has 2, C has 1. None has been claimed
            # before, so they start in id order: A, B, C, A, B, A.

            a = await make_source("a")
            b = await make_source("b")
            c = await make_source("c")

            a_deep = await make_target(a, "deep", priority=50, depth=2)
            a_shallow = await make_target(a, "shallow", priority=50, depth=0)
            a_reference = await make_target(a, "reference", priority=80, depth=3)
            b_one = await make_target(b, "one", priority=50, depth=0)
            b_two = await make_target(b, "two", priority=50, depth=1)
            c_one = await make_target(c, "one", priority=50, depth=0)

            claimed = await claim_targets(session, limit=6)

            check(len(claimed) == 6, "Six targets claimed in one call")
            check(
                [t.source_id for t in claimed]
                == [a.id, b.id, c.id, a.id, b.id, a.id],
                "Sources are claimed in turn: A, B, C, A, B, A",
            )

            # ==========================================
            # TEST 2: Priority, then depth, inside a source
            # ==========================================

            a_order = [t.id for t in claimed if t.source_id == a.id]
            check(
                a_order == [a_reference.id, a_shallow.id, a_deep.id],
                "Source A: priority 80 first, then depth 0 before depth 2",
            )
            check(
                [t.id for t in claimed if t.source_id == b.id]
                == [b_one.id, b_two.id],
                "Source B: depth 0 before depth 1 at equal priority",
            )
            check(
                all(t.state == "leased" for t in claimed),
                "Every claimed target is leased",
            )

            # ==========================================
            # TEST 3: last_claimed_at records each turn
            # ==========================================

            for source in (a, b, c):
                await session.refresh(source)

            check(
                None not in (a.last_claimed_at, b.last_claimed_at, c.last_claimed_at),
                "last_claimed_at is set on every source that was claimed",
            )
            check(
                c.last_claimed_at < b.last_claimed_at < a.last_claimed_at,
                "last_claimed_at follows the last turn of each source (C, B, A)",
            )

            check(
                await claim_targets(session, limit=5) == [],
                "Nothing left once every due target is leased",
            )

            # ==========================================
            # TEST 4: Least recently claimed source goes first
            # ==========================================
            # D was claimed 1 hour ago and E 2 hours ago, so E has waited
            # longest. Separate limit=1 calls must still alternate.

            now = await session.scalar(select(func.now()))
            d = await make_source("d", last_claimed_at=now - timedelta(hours=1))
            e = await make_source("e", last_claimed_at=now - timedelta(hours=2))

            await make_target(d, "one")
            await make_target(d, "two")
            await make_target(e, "one")
            await make_target(e, "two")

            first = await claim_targets(session, limit=1)
            second = await claim_targets(session, limit=1)
            third = await claim_targets(session, limit=1)

            check(first[0].source_id == e.id, "First call picks E (oldest last_claimed_at)")
            check(second[0].source_id == d.id, "Second call picks D, not E again")
            check(third[0].source_id == e.id, "Third call returns to E")

            # ==========================================
            # TEST 5: Disabled and not-due sources are skipped
            # ==========================================

            disabled = await make_source("disabled", is_enabled=False)
            not_due = await make_source("notdue")
            disabled_target = await make_target(disabled, "one")
            future_target = await make_target(not_due, "one", next_fetch_at=future)

            remaining = await claim_targets(session, limit=5)

            check(
                [t.source_id for t in remaining] == [d.id],
                "Only D's last due target is claimed",
            )

            await session.refresh(disabled_target)
            await session.refresh(future_target)
            await session.refresh(disabled)
            await session.refresh(not_due)

            check(disabled_target.state == "queued", "Disabled source's target stays queued")
            check(future_target.state == "queued", "Not-yet-due target stays queued")
            check(
                disabled.last_claimed_at is None and not_due.last_claimed_at is None,
                "Skipped sources keep last_claimed_at empty",
            )

            # ==========================================
            # TEST 6: source_id keeps every claim in one source
            # ==========================================

            h = await make_source("h")
            await make_target(h, "one")
            await make_target(h, "two")
            await make_target(h, "three")

            # Give the loop another candidate so the filter is what matters.
            other = await make_source("other")
            await make_target(other, "one")

            h_claims = await claim_targets(session, limit=2, source_id=h.id)
            check(
                len(h_claims) == 2 and all(t.source_id == h.id for t in h_claims),
                "source_id=H claims two targets, both from H",
            )

            h_rest = await claim_targets(session, limit=10, source_id=h.id)
            check(
                len(h_rest) == 1 and h_rest[0].source_id == h.id,
                "A larger limit stops at H's last due target",
            )

            # ==========================================
            # TEST 7: Lease length and validation
            # ==========================================

            lease_source = await make_source("lease")
            await make_target(lease_source, "one")

            before = await session.scalar(select(func.clock_timestamp()))
            leased = await claim_targets(
                session,
                limit=1,
                lease_seconds=120,
                source_id=lease_source.id,
            )
            lease_delta = (leased[0].lease_until - before).total_seconds()

            check(
                119 <= lease_delta <= 125,
                f"lease_until is about 120 s out ({lease_delta:.1f} s)",
            )

            for kwargs, label in (
                ({"limit": 0}, "limit=0"),
                ({"lease_seconds": 0}, "lease_seconds=0"),
                ({"source_id": 0}, "source_id=0"),
            ):
                try:
                    await claim_targets(session, **kwargs)
                except ValueError:
                    check(True, f"{label} raises ValueError")
                else:
                    check(False, f"{label} raises ValueError")

            log(Fore.YELLOW, "DONE", "All round-robin claim tests passed")

        finally:
            await transaction.rollback()
            log(Fore.YELLOW, "CLEANUP", "Test transaction rolled back")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(
            main(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    else:
        asyncio.run(main())
