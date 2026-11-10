"""Validate the database component before destructive benchmark setup."""
from sqlalchemy.engine import make_url


def benchmark_database_url(raw: str) -> str:
    try:
        parsed = make_url(raw)
    except Exception:
        raise ValueError("BENCH_DATABASE_URL must be a valid disposable PostgreSQL URL") from None
    if parsed.drivername != "postgresql+asyncpg" or "test" not in (parsed.database or "").casefold():
        raise ValueError("BENCH_DATABASE_URL must use asyncpg and a database name containing test")
    return raw
