
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.source import Source
from backend.schema.source import SourceCreate, SourceUpdate


class SourceNotFoundError(LookupError):
    pass


class SourceAlreadyExistsError(ValueError):
    pass


# ----------------------------------------
# READ: Get all registered sources
# ----------------------------------------

async def get_all_sources(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[Source]:

    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")

    if offset < 0:
        raise ValueError("offset cannot be negative")

    statement = (
        select(Source)
        .order_by(Source.id)
        .limit(limit)
        .offset(offset)
    )

    result = await session.scalars(statement)
    return list(result.all())


# ----------------------------------------
# READ: Get only enabled sources
# ----------------------------------------

async def get_enabled_sources(
    session: AsyncSession,
    limit: int = 100,
    offset: int = 0,
) -> list[Source]:

    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")

    if offset < 0:
        raise ValueError("offset cannot be negative")

    statement = (
        select(Source)
        .where(Source.is_enabled.is_(True))
        .order_by(Source.id)
        .limit(limit)
        .offset(offset)
    )

    result = await session.scalars(statement)
    return list(result.all())


# ----------------------------------------
# READ: Get source by ID
# ----------------------------------------

async def get_source_by_id(
    session: AsyncSession,
    source_id: int,
) -> Source | None:

    return await session.get(Source, source_id)


# ----------------------------------------
# READ: Get source by slug
# ----------------------------------------

async def get_source_by_slug(
    session: AsyncSession,
    slug: str,
) -> Source | None:

    statement = select(Source).where(
        Source.slug == slug
    )

    return await session.scalar(statement)


# ----------------------------------------
# CREATE: Register a new source
# ----------------------------------------

async def register_source(
    session: AsyncSession,
    data: SourceCreate,
) -> Source:

    values = data.model_dump(mode="json")

    statement = (
        insert(Source)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[Source.slug]
        )
        .returning(Source.id)
    )

    source_id = await session.scalar(statement)

    if source_id is None:
        raise SourceAlreadyExistsError(
            f"Source '{data.slug}' already exists"
        )

    source = await session.get(Source, source_id)

    if source is None:
        raise RuntimeError(
            "Inserted source could not be retrieved"
        )

    return source


# ----------------------------------------
# UPDATE: Modify source configuration
# ----------------------------------------

async def update_source(
    session: AsyncSession,
    source_id: int,
    data: SourceUpdate,
) -> Source:

    source = await session.get(Source, source_id)

    if source is None:
        raise SourceNotFoundError(
            f"Source with ID {source_id} not found"
        )

    updates = data.model_dump(
        mode="json",
        exclude_unset=True,
    )

    allowed_fields = {
        "name",
        "kind",
        "base_url",
        "allowed_hosts",
        "crawl_interval_seconds",
        "is_enabled",
        "config",
    }

    unexpected = set(updates) - allowed_fields

    if unexpected:
        raise ValueError(
            f"Fields cannot be updated: {sorted(unexpected)}"
        )

    for field, value in updates.items():
        setattr(source, field, value)

    await session.flush()

    return source


# ----------------------------------------
# UPDATE: Enable / Disable source
# ----------------------------------------

async def set_source_enabled(
    session: AsyncSession,
    source_id: int,
    enabled: bool,
) -> Source:

    source = await session.get(Source, source_id)

    if source is None:
        raise SourceNotFoundError(
            f"Source with ID {source_id} not found"
        )

    source.is_enabled = enabled

    await session.flush()

    return source
