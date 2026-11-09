"""FastAPI application and the periodically refreshed BM25 corpus snapshot."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.api.crawler_report import router as crawler_report_router
from backend.api.indexer_report import router as indexer_report_router
from backend.api.search import router as search_router
from backend.api.ai_overview import router as ai_overview_router
from backend.api.system_report import router as system_report_router
from backend.core.config import settings
from backend.db.session import SessionFactory, engine
from backend.search.ranking.statistics import get_corpus_statistics
from backend.search.service import clear_corpus_statistics, set_corpus_statistics
from backend.search.telemetry import telemetry

logger = logging.getLogger(__name__)

CORPUS_REFRESH_SECONDS = 600.0


async def load_corpus_statistics() -> None:
    async with SessionFactory() as session:
        text_corpus = await get_corpus_statistics(session, "TEXT")
        code_corpus = await get_corpus_statistics(session, "CODE")
    set_corpus_statistics(text_corpus, code_corpus)



async def refresh_corpus_statistics() -> None:
    """Refresh BM25 statistics every 10 minutes; retry after failures."""
    while True:
        await asyncio.sleep(600)

        try:
            await load_corpus_statistics()

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Corpus statistics refresh failed; "
                "preserving last good snapshot"
            )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    tasks = []
    try:
        await load_corpus_statistics()
        tasks = [asyncio.create_task(refresh_corpus_statistics()), asyncio.create_task(telemetry.run())]
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if tasks:
            await telemetry.flush_quietly()
        clear_corpus_statistics()
        await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.include_router(crawler_report_router)
app.include_router(indexer_report_router)
app.include_router(system_report_router)
app.include_router(search_router)
app.include_router(ai_overview_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def home() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health/db")
async def database_health() -> dict[str, str]:
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT current_database() AS database, current_user AS user")
        )
        row = result.mappings().one()
    return {"status": "ok", "database": row["database"], "user": row["user"]}
