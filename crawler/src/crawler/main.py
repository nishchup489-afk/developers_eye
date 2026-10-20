import sys
import argparse
import asyncio

from crawler.seed.seed import seed_sources
from crawler.seed.discovery import discover_initial_targets


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Developers Eye crawler"
    )

    parser.add_argument(
        "command",
        choices=["seed", "discover", "bootstrap"],
        help="Choose a crawler operation",
    )

    args = parser.parse_args()

    if args.command in ("seed", "bootstrap"):
        print("Registering sources...")
        await seed_sources()

    if args.command in ("discover", "bootstrap"):
        print("Discovering initial crawl targets...")

        inserted = await discover_initial_targets()

        print(f"New crawl targets inserted: {inserted}")

    print("Operation completed.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(
            main(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    else:
        asyncio.run(main())