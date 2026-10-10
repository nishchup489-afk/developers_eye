
import asyncio
import json

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert

from backend.db.session import SessionFactory
from backend.models.source import Source
from backend.schema.source import SourceCreate


SOURCES_DIR = Path(__file__).resolve().parent / "sources"


def load_source() -> list[dict[str, Any]]:
    sources = []
    seen_slugs = set()

    if not SOURCES_DIR.is_dir():
        raise FileNotFoundError(
            f"Source directory not found: {SOURCES_DIR}"
        )

    for path in sorted(SOURCES_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in {path.name}: {exc}"
            ) from exc

        if not isinstance(data, list):
            raise ValueError(
                f"{path.name} must contain a JSON array"
            )

        for idx, entry in enumerate(data, start=1):
            try:
                source = SourceCreate.model_validate(entry)
            except ValidationError as exc:
                raise ValueError(
                    f"Invalid source in {path.name}, entry {idx}"
                ) from exc

            if source.slug in seen_slugs:
                raise ValueError(
                    f"Duplicate source slug: {source.slug}"
                )

            seen_slugs.add(source.slug)

            sources.append(
                source.model_dump(mode="json")
            )

    return sources


async def seed_sources() -> None:
    sources = load_source()

    if not sources:
        print("No sources found.")
        return

    async with SessionFactory() as session:
        async with session.begin():
            statement = (
                insert(Source)
                .values(sources)
                .on_conflict_do_nothing(
                    index_elements=[Source.slug]
                )
                .returning(Source.id)
            )

            result = await session.scalars(statement)
            inserted_count = len(result.all())

    print(f"Sources loaded: {len(sources)}")
    print(f"New sources inserted: {inserted_count}")


if __name__ == "__main__":
    asyncio.run(seed_sources())
