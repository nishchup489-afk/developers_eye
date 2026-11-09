"""Read shared generation reservations; these are conservative budgets, not billing."""
from sqlalchemy import func, select
from backend.core.config import settings
from backend.models.ai_overview import OverviewBudget


async def build_ai_usage(session):
    now = (await session.scalar(select(func.clock_timestamp()))).timestamp()
    budget = await session.get(OverviewBudget, "groq")
    state = budget.state if budget else {}
    windows = []
    for name, seconds, requests, tokens in [("Last minute", 60, 20, 5000), ("Last 24 hours", 86400, 800, 160000)]:
        entries = [entry for entry in state.get("day", []) if entry[0] > now - seconds]
        windows.append(dict(name=name, requests=len(entries), request_limit=requests,
                            reserved_tokens=sum(entry[1] for entry in entries), token_limit=tokens))
    return dict(model=settings.groq_model, windows=windows,
                cooldown_seconds=max(0, int(state.get("blocked_until", 0) - now)),
                accounting="Reserved token budgets including failed calls; not actual provider billing. Cache hits do not reserve tokens.")
