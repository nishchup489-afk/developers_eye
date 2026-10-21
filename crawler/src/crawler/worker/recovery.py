"""Finish failed claims independently after the job transaction rolls back."""
import logging

from sqlalchemy import select

from backend.models.crawler_frontier import CrawlTarget
from crawler.schedular.repository import fail_target
from crawler.writer.attempts import close_abandoned_attempts

logger = logging.getLogger(__name__)


async def recover_failed_claim(factory, target_id, lease_until, category, message):
    try:
        async with factory() as session, session.begin():
            target = await session.scalar(select(CrawlTarget).where(CrawlTarget.id == target_id).with_for_update())
            owns_claim = target is not None and target.state == 'leased' and target.lease_until == lease_until
            await close_abandoned_attempts(session, target_id, category, message,
                lease_until=lease_until, include_legacy=owns_claim)
            if owns_claim:
                await fail_target(session, target_id, lease_until)
    except Exception:
        # A database outage leaves the exact claim for expiration recovery.
        logger.exception('Could not recover failed target=%s; lease recovery remains pending', target_id)
