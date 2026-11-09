"""Coordinate evidence, durable quotas and shared generation leases (ADR-0049)."""
import asyncio
import hashlib
import logging

from sqlalchemy.exc import SQLAlchemyError

from backend.ai_overview import provider
from backend.ai_overview.prompt import SYSTEM_PROMPT, TOKEN_BUDGET, build_evidence
from backend.ai_overview.store import Outcome, store
from backend.core.config import settings
from backend.schema.ai_overview import OverviewContext

logger = logging.getLogger(__name__)


async def overview(context: OverviewContext, client: str) -> Outcome:
    content, tokens = build_evidence(context)
    if tokens > TOKEN_BUDGET:
        return Outcome()
    # Expiry is excluded: two searches with identical evidence share their answer.
    key = hashlib.sha256((settings.groq_model + SYSTEM_PROMPT + context.model_dump_json(exclude={"expires"})).encode()).hexdigest()
    try:
        async with asyncio.timeout(16):
            while True:
                claim = await store.claim(key, client, tokens)
                if claim.outcome is not None:
                    return claim.outcome
                if claim.owner:
                    outcome = await provider.generate(context, content)
                    await store.finish(key, claim.owner, outcome)
                    return outcome
                await asyncio.sleep(0.2)
    except TimeoutError:
        return Outcome(status=504, error="AI overview timed out. Explore the sources below.")
    except (SQLAlchemyError, OSError):
        # No fallback to process-local limits. Search remains independent.
        logger.warning("AI overview state unavailable", exc_info=False)
        return Outcome(status=503, retry_after=5, error="AI overview is unavailable right now. Explore the sources below.")
