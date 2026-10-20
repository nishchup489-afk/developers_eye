"""PostgreSQL integration tests for Developer's Eye database writers.

Runs against a DEDICATED TEST DATABASE ONLY.
No HTTP calls. No crawler worker. Each test rolls back its seeded data.

Run from crawler/:
    poetry run pytest -v -s src/crawler/writer/tests/test_writer.py

Prerequisite:
    Set TEST_DATABASE_URL to a PostgreSQL+asyncpg DSN whose database name
    contains "test", e.g. postgresql+asyncpg://postgres:pass@localhost/developers_eye_test
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Import all models to register their tables/foreign keys with Base.metadata.
import backend.models  # noqa: F401
from backend.db.base import Base
from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.source import Source

from crawler.parser.schemas import ParsedDocument
from crawler.processing import process_document
from crawler.writer.attempts import start_attempt, finish_attempt
from crawler.writer.documents import upsert_document

try:
    from colorama import Fore, Style, just_fix_windows_console
    just_fix_windows_console()
except ImportError:
    class _NoColor:
        GREEN = RED = CYAN = YELLOW = RESET_ALL = ""
    Fore = Style = _NoColor()


def note(message: str) -> None:
    print(f"\n{Fore.CYAN}  [WRITER TEST] {message}{Style.RESET_ALL}")


def passed(message: str) -> None:
    print(f"{Fore.GREEN}  [PASS] {message}{Style.RESET_ALL}")


def _test_db_url() -> str:
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.fail(
            "Set TEST_DATABASE_URL to a dedicated PostgreSQL test database. "
            "Do not point this test at your actual crawler database."
        )
    try:
        url = make_url(raw)
    except Exception as exc:
        pytest.fail(f"Invalid TEST_DATABASE_URL: {exc}")

    if url.drivername != "postgresql+asyncpg":
        pytest.fail("TEST_DATABASE_URL must use postgresql+asyncpg://")
    if not url.database or "test" not in url.database.casefold():
        pytest.fail(
            "Safety check: the database NAME must contain 'test' "
            "(example: developers_eye_test)."
        )
    return raw


@asynccontextmanager
async def writer_db():
    """Create schema if absent, then provide seeded rows under rollback isolation.

    DDL setup is committed to the dedicated test DB. Test-created rows are not.
    """
    engine = create_async_engine(_test_db_url(), echo=False, pool_pre_ping=True)
    try:
        # For convenience on a fresh dedicated test DB. Production DB is never used.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with engine.connect() as conn:
            outer = await conn.begin()
            try:
                async with AsyncSession(
                    bind=conn,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    async with session.begin():
                        token = uuid4().hex
                        source = Source(
                            slug=f"writer-test-{token}",
                            name="Writer integration test",
                            kind="website",
                            base_url="https://example.com/",
                            allowed_hosts=["example.com"],
                            crawl_interval_seconds=3600,
                            is_enabled=True,
                            config={},
                        )
                        session.add(source)
                        await session.flush()

                        target = CrawlTarget(
                            source_id=source.id,
                            fetch_url="https://example.com/docs",
                            normalized_url="https://example.com/docs",
                            kind="page",
                            state="leased",
                            priority=0,
                            failure_count=0,
                        )
                        session.add(target)
                        await session.flush()

                    yield session, source, target
            finally:
                if outer.is_active:
                    await outer.rollback()
    finally:
        await engine.dispose()


def make_document(
    *,
    body: str = "A developer guide to Python asyncio.",
    author: str = "Example Team",
    tag: str = "python",
):
    """Use the REAL content processing pipeline, not a mock model."""
    parsed = ParsedDocument(
        url="https://example.com/docs",
        title="  Python   Asyncio Guide  ",
        description="  Learn async Python.  ",
        body=body,
        author=author,
        headings=("Getting Started",),
        code_blocks=("async def main():\n    pass",),
        metadata={"tag": tag},
    )
    return process_document(parsed)


def test_attempt_starts_and_finishes():
    async def run():
        async with writer_db() as (session, source, target):
            note("Create unfinished crawl_attempt row")
            async with session.begin():
                attempt_id = await start_attempt(session, target.id)
            assert isinstance(attempt_id, int) and attempt_id > 0

            async with session.begin():
                pending = await session.get(CrawlAttempt, attempt_id)
                assert pending is not None
                assert pending.outcome is None
                assert pending.finished_at is None
                assert pending.crawl_target_id == target.id
            passed(f"started crawl_attempt #{attempt_id}")

            note("Finish attempt, including HTTP status and bytes")
            async with session.begin():
                updated = await finish_attempt(
                    session, attempt_id, "success",
                    http_status=200, bytes_received=1234,
                )
                assert updated is True
            async with session.begin():
                saved = await session.get(CrawlAttempt, attempt_id)
                await session.refresh(saved)
                assert saved.outcome == "success"
                assert saved.http_status == 200
                assert saved.bytes_received == 1234
                assert saved.finished_at is not None
                assert saved.finished_at >= saved.started_at
            passed("success / 200 / 1234 bytes recorded")

    asyncio.run(run())


def test_attempt_cannot_be_finished_twice():
    async def run():
        async with writer_db() as (session, source, target):
            async with session.begin():
                attempt_id = await start_attempt(session, target.id)

            note("First finish should succeed; second must not overwrite it")
            async with session.begin():
                assert await finish_attempt(
                    session, attempt_id, "failed", error_message="Timeout"
                )
                assert not await finish_attempt(
                    session, attempt_id, "success", http_status=200
                )
            async with session.begin():
                saved = await session.get(CrawlAttempt, attempt_id)
                await session.refresh(saved)
                assert saved.outcome == "failed"
                assert saved.error_message == "Timeout"
            passed("duplicate completion rejected; original outcome preserved")

    asyncio.run(run())


def test_attempt_validates_inputs():
    async def run():
        async with writer_db() as (session, source, target):
            note("Reject invalid IDs, statuses, bytes, and outcomes")
            async with session.begin():
                with pytest.raises(ValueError):
                    await start_attempt(session, 0)
                attempt_id = await start_attempt(session, target.id)
                with pytest.raises(ValueError):
                    await finish_attempt(session, attempt_id, "unknown")
                with pytest.raises(ValueError):
                    await finish_attempt(session, attempt_id, "success", http_status=999)
                with pytest.raises(ValueError):
                    await finish_attempt(session, attempt_id, "success", bytes_received=-1)
            passed("invalid inputs rejected")

    asyncio.run(run())


def test_document_insert_and_unchanged_recrawl():
    async def run():
        async with writer_db() as (session, source, target):
            document = make_document()

            note("First crawl: INSERT document")
            async with session.begin():
                doc_id = await upsert_document(
                    session, document, source_id=source.id, crawl_target_id=target.id
                )
            async with session.begin():
                saved = await session.get(Document, doc_id)
                await session.refresh(saved)
                original_updated_at = saved.updated_at
                original_seen_at = saved.last_seen_at
                assert saved.title == "Python Asyncio Guide"
                assert saved.document_type == "documentation"
                assert saved.content_hash == document.content_hash
                assert saved.metadata_["code_blocks"]
            passed(f"document #{doc_id} inserted with correct metadata and hash")

            await asyncio.sleep(0.05)

            note("Second crawl, same data: UPSERT without changing updated_at")
            async with session.begin():
                second_id = await upsert_document(
                    session, document, source_id=source.id, crawl_target_id=target.id
                )
            assert second_id == doc_id
            async with session.begin():
                saved = await session.get(Document, doc_id)
                await session.refresh(saved)
                assert saved.updated_at == original_updated_at
                assert saved.last_seen_at > original_seen_at
                count = await session.scalar(
                    select(Document.id).where(Document.canonical_url == document.canonical_url)
                )
                assert count == doc_id
            passed("same ID; last_seen_at refreshed; updated_at unchanged")

    asyncio.run(run())


def test_changed_content_updates_existing_document():
    async def run():
        async with writer_db() as (session, source, target):
            first = make_document(body="Version one of the Python guide.")
            second = make_document(body="Version two, now with asyncio examples.")
            assert first.content_hash != second.content_hash

            async with session.begin():
                doc_id = await upsert_document(
                    session, first, source_id=source.id, crawl_target_id=target.id
                )
            async with session.begin():
                saved = await session.get(Document, doc_id)
                await session.refresh(saved)
                previous_updated = saved.updated_at
            await asyncio.sleep(0.05)

            note("Changed body/hash should UPDATE, not INSERT")
            async with session.begin():
                updated_id = await upsert_document(
                    session, second, source_id=source.id, crawl_target_id=target.id
                )
            assert updated_id == doc_id
            async with session.begin():
                saved = await session.get(Document, doc_id)
                await session.refresh(saved)
                assert saved.body == second.body
                assert saved.content_hash == second.content_hash
                assert saved.updated_at > previous_updated
            passed("same ID, changed body/hash and newer updated_at")

    asyncio.run(run())


def test_metadata_only_change_counts_as_update():
    async def run():
        async with writer_db() as (session, source, target):
            first = make_document(tag="python")
            second = make_document(tag="asyncio")
            assert first.content_hash == second.content_hash

            async with session.begin():
                doc_id = await upsert_document(
                    session, first, source_id=source.id, crawl_target_id=target.id
                )
            async with session.begin():
                old = await session.get(Document, doc_id)
                await session.refresh(old)
                old_time = old.updated_at
            await asyncio.sleep(0.05)

            note("Metadata changes even when content_hash stays the same")
            async with session.begin():
                await upsert_document(
                    session, second, source_id=source.id, crawl_target_id=target.id
                )
            async with session.begin():
                saved = await session.get(Document, doc_id)
                await session.refresh(saved)
                assert saved.content_hash == first.content_hash
                assert saved.metadata_["tag"] == "asyncio"
                assert saved.updated_at > old_time
            passed("metadata-only change detected")

    asyncio.run(run())


def test_writer_respects_worker_transaction_rollback():
    async def run():
        async with writer_db() as (session, source, target):
            note("Rollback simulates Worker abandoning a transaction")
            async with session.begin() as transaction:
                attempt_id = await start_attempt(session, target.id)
                await upsert_document(
                    session, make_document(),
                    source_id=source.id, crawl_target_id=target.id
                )
                await transaction.rollback()

            async with session.begin():
                attempt = await session.get(CrawlAttempt, attempt_id)
                doc = await session.scalar(
                    select(Document).where(Document.canonical_url == "https://example.com/docs")
                )
                assert attempt is None
                assert doc is None
            passed("uncommitted attempt and document were rolled back")

    asyncio.run(run())
