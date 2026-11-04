"""Telemetry retention for the admin dashboard's crawl history.

crawl_event holds about seven rows per attempt, so at millions of attempts it
becomes one of the largest tables. Attempts keep their summary telemetry, so the
daily charts and source tables still work after events are purged; only the
per-attempt stage timeline disappears for old attempts.

Run from backend/ (schedule it daily with cron or Task Scheduler):
    python -m backend.admin_services.maintenance --purge-events
    python -m backend.admin_services.maintenance --purge-events --days 7 --dry-run
"""
import argparse
import asyncio
import selectors
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from backend.core.config import settings
from backend.models.crawl_monitor import CrawlEvent

BATCH = 5000


async def purge_events(factory, *, days: int, batch: int = BATCH, dry_run: bool = False) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if dry_run:
        async with factory() as session:
            return int(await session.scalar(select(func.count(CrawlEvent.id)).where(CrawlEvent.created_at < cutoff)))
    removed = 0
    while True:
        # Short transactions: workers keep writing events while this runs.
        async with factory() as session, session.begin():
            ids = select(CrawlEvent.id).where(CrawlEvent.created_at < cutoff).order_by(CrawlEvent.id).limit(batch).scalar_subquery()
            result = await session.execute(delete(CrawlEvent).where(CrawlEvent.id.in_(ids)))
        removed += result.rowcount or 0
        if not result.rowcount or result.rowcount < batch:
            return removed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Developer's Eye admin telemetry maintenance")
    parser.add_argument("--purge-events", action="store_true", help="delete crawl_event rows past retention")
    parser.add_argument("--days", type=int, default=settings.admin_event_retention_days)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--dry-run", action="store_true", help="count rows that would be deleted")
    args = parser.parse_args(argv)
    if args.days < 1 or args.batch < 1:
        parser.error("--days and --batch must be positive")
    return args


async def main(args) -> int:
    from backend.db.session import SessionFactory, engine
    try:
        if not args.purge_events:
            print("Nothing to do. Pass --purge-events.")
            return 0
        count = await purge_events(SessionFactory, days=args.days, batch=args.batch, dry_run=args.dry_run)
        print(f"{'Would delete' if args.dry_run else 'Deleted'} {count} crawl events older than {args.days} days.")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    arguments = parse_args()
    if sys.platform == "win32":
        raise SystemExit(asyncio.run(main(arguments), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())))
    raise SystemExit(asyncio.run(main(arguments)))
