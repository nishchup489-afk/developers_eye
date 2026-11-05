from collections.abc import AsyncGenerator 

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings 


engine = create_async_engine(
    settings.database_url , 
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
)


SessionFactory = async_sessionmaker(
    bind=engine , 
    class_=AsyncSession ,
    expire_on_commit=False , 
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession , None]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
