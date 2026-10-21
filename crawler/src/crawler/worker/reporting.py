"""Compatibility CLI for the backend-owned, read-only crawler report."""
import asyncio
import selectors
import sys

from backend.services.crawler_reporting import (
    _utc, _percentage, build_report, format_text_report, main, parse_args,
)

if __name__ == "__main__":
    args = parse_args()
    if sys.platform == "win32":
        result = asyncio.run(
            main(args),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
    else:
        result = asyncio.run(main(args))
    raise SystemExit(result)
