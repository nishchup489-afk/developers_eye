"""Push dashboard problems to a phone or inbox, for a free cron-driven alert.

Posts warning and critical problems to ADMIN_ALERT_URL (for example an
https://ntfy.sh/<your-private-topic> URL) only when the set of problems
changes, so a five-minute schedule does not repeat the same alert.

Run from backend/:
    python -m backend.admin_services.alerts            # send if changed
    python -m backend.admin_services.alerts --print    # show, send nothing
"""
import argparse
import asyncio
import json
import os
import selectors
import sys
import urllib.request
from pathlib import Path

from sqlalchemy import text

from backend.admin_services.system_reporting import build_problems

STATE = Path(os.environ.get("ADMIN_ALERT_STATE", Path.home() / ".developers-eye-alerts.json"))


def alert_text(problems) -> str:
    lines = [f"[{p['severity'].upper()}] {p['title']}: {p['detail']}" for p in problems]
    return "\n".join(lines) if lines else "All clear: no admin problems."


def changed(problems, state: Path = STATE) -> bool:
    current = sorted(p["id"] for p in problems)
    try:
        previous = json.loads(state.read_text())
    except (OSError, ValueError):
        previous = None
    if previous == current:
        return False
    state.write_text(json.dumps(current))
    return True


def send(url: str, body: str, *, priority: str) -> None:
    request = urllib.request.Request(url, data=body.encode(), method="POST",
        headers={"Title": "Developer's Eye admin", "Priority": priority, "Content-Type": "text/plain; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


async def main(args) -> int:
    from backend.db.session import SessionFactory, engine
    try:
        async with SessionFactory() as session:
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            report = await build_problems(session)
    finally:
        await engine.dispose()
    urgent = [p for p in report["problems"] if p["severity"] in ("critical", "warning")]
    body = alert_text(urgent)
    if args.print:
        print(body)
        return 0
    url = os.environ.get("ADMIN_ALERT_URL", "")
    if not url.startswith("https://"):
        print("Set ADMIN_ALERT_URL to an https:// endpoint (for example an ntfy.sh topic).", file=sys.stderr)
        return 2
    if changed(urgent):
        send(url, body, priority="high" if any(p["severity"] == "critical" for p in urgent) else "default")
        print("Alert sent.")
    else:
        print("No change since the last alert.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send admin problems to ADMIN_ALERT_URL")
    parser.add_argument("--print", action="store_true", help="print problems without sending")
    arguments = parser.parse_args()
    if sys.platform == "win32":
        raise SystemExit(asyncio.run(main(arguments), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())))
    raise SystemExit(asyncio.run(main(arguments)))
