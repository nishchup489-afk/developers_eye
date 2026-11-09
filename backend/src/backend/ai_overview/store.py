"""PostgreSQL reservations, cache and leases shared by every API worker (ADR-0049)."""
from dataclasses import asdict, dataclass
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

from backend.ai_overview.limits import reserve
from backend.db.session import SessionFactory
from backend.models.ai_overview import OverviewBudget, OverviewCache


@dataclass
class Outcome:
    overview: dict | None = None
    status: int = 200
    error: str | None = None
    retry_after: int | None = None

    def body(self):
        return {"overview": self.overview, **({"error": self.error} if self.error else {})}


@dataclass
class Claim:
    owner: str | None = None
    outcome: Outcome | None = None


class OverviewStore:
    def __init__(self, session_factory=SessionFactory):
        self.session_factory = session_factory

    async def _lock(self, session):
        await session.execute(text("SET LOCAL lock_timeout = '2s'"))
        await session.execute(text("SET LOCAL statement_timeout = '2s'"))
        await session.execute(insert(OverviewBudget).values(scope="groq", state={}).on_conflict_do_nothing())
        budget = await session.scalar(select(OverviewBudget).where(OverviewBudget.scope == "groq").with_for_update())
        now = (await session.scalar(select(func.clock_timestamp()))).timestamp()
        return budget, now

    async def claim(self, key: str, client: str, tokens: int) -> Claim:
        async with self.session_factory() as session, session.begin():
            budget, now = await self._lock(session)
            entry = await session.get(OverviewCache, key)
            if entry and entry.payload is not None and entry.expires_at > now:
                return Claim(outcome=Outcome(**entry.payload))
            if entry and entry.lease_until > now:
                return Claim()  # Another worker owns generation; wait for its cached outcome.
            state, retry = reserve(budget.state, client, tokens, now)
            budget.state = state
            if retry:
                return Claim(outcome=Outcome(status=429, retry_after=retry,
                    error="AI overview is busy. Your search results are ready below."))
            # Bound storage without deleting active generation leases.
            await session.execute(delete(OverviewCache).where(OverviewCache.expires_at <= now,
                                                               OverviewCache.lease_until <= now,
                                                               OverviewCache.key != key))
            stale_keys = select(OverviewCache.key).where(OverviewCache.lease_until <= now, OverviewCache.key != key).order_by(
                OverviewCache.expires_at.desc()).offset(499)
            await session.execute(delete(OverviewCache).where(OverviewCache.key.in_(stale_keys)))
            owner = uuid4().hex
            if entry is None:
                entry = OverviewCache(key=key, payload=None, expires_at=0, lease_until=0)
                session.add(entry)
            entry.lease_owner, entry.lease_until = owner, now + 30
            entry.payload, entry.expires_at = None, 0
            return Claim(owner=owner)

    async def finish(self, key: str, owner: str, outcome: Outcome) -> None:
        async with self.session_factory() as session, session.begin():
            budget, now = await self._lock(session)
            # Cooldowns apply even if the original generation lease has expired.
            if outcome.status == 429:
                budget.state = {**budget.state, "blocked_until": max(budget.state.get("blocked_until", 0), now + (outcome.retry_after or 60))}
            entry = await session.get(OverviewCache, key)
            if entry is None or entry.lease_owner != owner:
                return  # A stale worker must never overwrite a newer lease/result.
            ttl = (1800 if outcome.overview else 300) if outcome.status == 200 else 5
            entry.payload, entry.expires_at = asdict(outcome), now + ttl
            entry.lease_owner, entry.lease_until = None, 0


store = OverviewStore()
