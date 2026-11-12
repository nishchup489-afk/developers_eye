"""Preview derived category repairs; pass --apply to persist them. No crawling."""
import argparse
import asyncio
import json
from sqlalchemy import text
from backend.db.session import SessionFactory, engine
from backend.admin_services.category_maintenance import refresh_categories


async def main(apply):
    try:
        async with SessionFactory() as session, session.begin():
            if not apply:
                await session.execute(text("SET TRANSACTION READ ONLY"))
            result = await refresh_categories(session, apply=apply)
        print(json.dumps(result, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
