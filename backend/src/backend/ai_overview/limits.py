"""Pure sliding-window reservation; store.py serializes it across all workers."""
from copy import deepcopy
from math import ceil


def reserve(state: dict, client: str, tokens: int, now: float) -> tuple[dict, int]:
    state = deepcopy(state)
    minute = state["minute"] = [entry for entry in state.get("minute", []) if entry[0] > now - 60]
    day = state["day"] = [entry for entry in state.get("day", []) if entry[0] > now - 86400]
    clients = state["clients"] = {
        key: [at for at in timestamps if at > now - 86400]
        for key, timestamps in state.get("clients", {}).items() if timestamps and timestamps[-1] > now - 86400
    }
    user_day = clients.get(client, [])
    user_minute = [at for at in user_day if at > now - 60]
    waits = [state.get("blocked_until", 0) - now]
    for entries, duration, requests, budget in [(minute, 60, 20, 5000), (day, 86400, 800, 160000)]:
        count, used = len(entries), sum(entry[1] for entry in entries)
        for at, amount in entries:
            if count < requests and used + tokens <= budget:
                break
            waits.append(at + duration - now)
            count -= 1
            used -= amount
        if tokens > budget:
            waits.append(duration)
    if len(user_minute) >= 3:
        waits.append(user_minute[0] + 60 - now)
    if len(user_day) >= 30:
        waits.append(user_day[0] + 86400 - now)
    retry = ceil(max(0, *waits))
    if not retry:
        minute.append([now, tokens])
        day.append([now, tokens])
        clients[client] = [*user_day, now]
    return state, retry
