
import asyncio
import selectors
import sys
from uuid import uuid4

from sqlalchemy import select

from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate

from crawler.frontier.repository import enqueue_target
from crawler.frontier.urls import normalize_url


async def main():
    async with SessionFactory() as session:
        async with session.begin():

            # 1. Find an existing enabled source
            source_id = await session.scalar(
                select(Source.id)
                .where(Source.is_enabled.is_(True))
                .limit(1)
            )

            if source_id is None:
                raise RuntimeError(
                    "No enabled source found. Run your source seeder first."
                )

            # 2. Generate a unique test URL
            url = f"https://example.com/test/{uuid4().hex}"

            # 3. Construct and validate target
            target = CrawlTargetCreate(
                source_id=source_id,
                fetch_url=url,
                normalized_url=normalize_url(url),
                kind="page",
            )

            # 4. First insertion
            first = await enqueue_target(session, target)

            # 5. Attempt inserting same target again
            second = await enqueue_target(session, target)

            print(f"First insertion:  {first}")
            print(f"Second insertion: {second}")

            # 6. Verify expected results
            assert first is True
            assert second is False

            print("TEST PASSED")

            # 7. Roll back test data
            await session.rollback()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(
            main(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
    else:
        asyncio.run(main())