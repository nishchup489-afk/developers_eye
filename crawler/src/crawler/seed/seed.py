# what it does?it insert the registry in source table of postgres 


import json

from backend.core.config import settings
from backend.db.session import SessionFactory
from backend.models.source import Source

from pydantic import ValidationError
from sqlalchemy import insert, select 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.orm import selectinload 

from backend.schema.source import SourceCreate , SourceRead , SourceUpdate

from pathlib import Path 


SOURCES_DIR = Path(__file__).resolve().parent/"sources"



def load_source() -> list[dict[str , any]]:
    sources = []
    seen_slugs = set()

    for path in sorted(SOURCES_DIR.glob("*.json")):
        with path.open("r" , encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data , list):
            raise ValueError(f"{path.name} must contain a json array")

        for idx , entry in enumerate(data , start=1):
            try:
                source = SourceCreate.model_dump(entry)
            except ValidationError as e:
                raise ValueError(
                    f"Invalid source in {path.name} , entry {idx}"
                ) from e 

            seen_slugs.add(sources.slug)

            sources.append(
                source.model_dump(mode=json)
            )

    return sources

async def seed_sources() -> None:
    sources = load_source() 

    if not sources:
        print(f"No sources found")
        return 

    async with SessionFactory() as session:
        async with session.begin():
            statement = (
                insert(Source)
                .values(sources)
                .on_conflict_do_nothing(
                    index_elements = [Source.slug]
                )
                .returning(Source.id)
            )

            result = await session.scalars(statement)
            inserted_count = len(result.all())
            
        print(f"Sources loaded : {len(sources)}")
        print(f"new source inserted : {inserted_count}")