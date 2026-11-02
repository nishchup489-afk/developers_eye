"""FastAPI application and startup-time BM25 corpus snapshot initialization."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api.crawler_report import router as crawler_report_router
from backend.api.indexer_report import router as indexer_report_router
from backend.api.search import router as search_router
from backend.core.config import settings
from backend.db.session import SessionFactory, engine
from backend.search.ranking.statistics import get_corpus_statistics
from backend.search.service import clear_corpus_statistics, set_corpus_statistics


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Full corpus scans happen at startup, never on individual search calls."""
    try:
        async with SessionFactory() as session:
            text_corpus = await get_corpus_statistics(session, "TEXT")
            code_corpus = await get_corpus_statistics(session, "CODE")
        set_corpus_statistics(text_corpus, code_corpus)
        yield
    finally:
        clear_corpus_statistics()
        await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.include_router(crawler_report_router)
app.include_router(indexer_report_router)
app.include_router(search_router)
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
