"""Alembic upgrades against a populated database.

Each test creates its own database on the TEST_DATABASE_URL server and drops it
afterwards. Requires a role allowed to CREATE DATABASE and CREATE EXTENSION.
    poetry run python -m pytest tests/integration/test_migrations.py -v
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[2]
BEFORE_CODE_VECTOR = "e94b530df145"
CODE_VECTOR = "28efc23fadfc"
OTHER_DOCUMENT_HASH = "v1:" + "a" * 64


def _dsn(url, database: str) -> str:
    return url.set(drivername="postgresql", database=database).render_as_string(hide_password=False)


def _sql(dsn: str, *statements: str) -> list:
    async def run():
        connection = await asyncpg.connect(dsn)
        try:
            rows = []
            for statement in statements:
                rows.append(await connection.fetch(statement))
            return rows
        finally:
            await connection.close()

    return asyncio.run(run())


@pytest.fixture
def database():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw or "test" not in (make_url(raw).database or ""):
        pytest.skip("Set TEST_DATABASE_URL to a PostgreSQL database whose name contains 'test'")
    url = make_url(raw)
    name = f"migration_test_{uuid4().hex[:10]}"
    admin = _dsn(url, url.database)
    _sql(admin, f'CREATE DATABASE "{name}"')
    try:
        yield url.set(database=name)
    finally:
        _sql(admin, f'DROP DATABASE "{name}" WITH (FORCE)')


def _alembic(url, *arguments: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=180,
    )


def _upgrade(url, revision: str) -> None:
    result = _alembic(url, "upgrade", revision)
    assert result.returncode == 0, result.stderr[-3000:]


def _populate(dsn: str) -> None:
    _sql(
        dsn,
        """
        INSERT INTO source (slug, name, kind, base_url, allowed_hosts, crawl_interval_seconds, is_enabled, config)
        VALUES ('docs', 'Docs', 'website', 'https://docs.example.com/', ARRAY['docs.example.com'], 60, true, '{}')
        """,
        """
        INSERT INTO document (source_id, canonical_url, document_type, title, body, content_hash, metadata)
        SELECT id, 'https://docs.example.com/' || n, 'article', 'Title', 'async await body', 'hash' || n, '{}'
        FROM source, generate_series(1, 3) AS n
        """,
        f"""
        INSERT INTO search_index (document_id, search_vector, indexed_hash)
        SELECT id, to_tsvector('english', title || ' ' || body), '{OTHER_DOCUMENT_HASH}' FROM document
        """,
    )


def test_code_vector_upgrade_keeps_a_populated_index_and_requeues_it(database):
    _upgrade(database, BEFORE_CODE_VECTOR)
    dsn = _dsn(database, database.database)
    _populate(dsn)

    _upgrade(database, CODE_VECTOR)

    [rows, column] = _sql(
        dsn,
        "SELECT code_vector::text AS code, search_vector::text AS text, indexed_hash FROM search_index",
        """
        SELECT is_nullable, column_default FROM information_schema.columns
        WHERE table_name = 'search_index' AND column_name = 'code_vector'
        """,
    )
    assert len(rows) == 3
    assert {row["code"] for row in rows} == {""}
    assert all("async" in row["text"] for row in rows), "the existing text index must survive"
    assert not any(row["indexed_hash"].startswith("v1:") for row in rows), (
        "rows without a real code vector must look outdated to the indexer"
    )
    assert column[0]["is_nullable"] == "NO"
    assert column[0]["column_default"] is None, "a default would hide a writer that forgets code_vector"

    _upgrade(database, "head")


def test_code_vector_upgrade_works_on_an_empty_table(database):
    _upgrade(database, BEFORE_CODE_VECTOR)
    _upgrade(database, "head")


def test_head_indexes_the_404_document_lookup(database):
    _upgrade(database, "head")
    [rows] = _sql(
        _dsn(database, database.database),
        "SELECT indisvalid FROM pg_index WHERE indexrelid = 'ix_document_last_crawl_target_id'::regclass",
    )
    assert [row["indisvalid"] for row in rows] == [True]
