from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI 
from sqlalchemy import text 

from backend.core.config import settings
from backend.db.session import engine 


from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(_:FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose() 


app = FastAPI(
    title= settings.app_name,
    version="1.0.0" , 
    lifespan=lifespan
)


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
async def home():
    return {
        "status" : "ok",
        "service" : settings.app_name
    }

@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }

@app.get("/health/db")
async def database_health() -> dict[str, str]:
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT
                    current_database() AS database,
                    current_user AS user
                """
            )
        )

        row = result.mappings().one()

    return {
        "status": "ok",
        "database": row["database"],
        "user": row["user"],
    }