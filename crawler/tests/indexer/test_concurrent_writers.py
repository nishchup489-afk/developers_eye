"""A crawler write and an index write on one document, in every order (PostgreSQL).

Needs TEST_DATABASE_URL: a migrated, dedicated database with "test" in its name.
"""
import asyncio
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, insert, literal, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.search_terms import VocabularyChange
from backend.models.source import Source
from crawler.processing import ProcessedDocument
from crawler.writer.documents import upsert_document
from indexer.config import IndexerConfig
from indexer.schemas import IndexStatus
from indexer.selector import is_index_current
from indexer.vector import SearchVectors
from indexer.writer import persist_search_vectors

HASH = "v1:" + "a" * 64
CONFIG = IndexerConfig()


@pytest_asyncio.fixture
async def db():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw or "test" not in (make_url(raw).database or ""):
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL database with test in its name")
    engine = create_async_engine(raw, connect_args={"server_settings": {"lock_timeout": "10000"}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    # Letters only, so the vocabulary filter keeps it as a term.
    tag = "".join(chr(97 + int(c, 16)) for c in uuid4().hex[:16])
    url = f"https://example.com/{tag}"
    async with factory() as session, session.begin():
        source_id = await session.scalar(insert(Source).values(
            slug=f"writers-{tag}", name="Writers test", kind="website", base_url="https://example.com/",
            allowed_hosts=["example.com"], crawl_interval_seconds=3600, is_enabled=True, config={},
        ).returning(Source.id))
        target_id = await session.scalar(insert(CrawlTarget).values(
            source_id=source_id, fetch_url=url, normalized_url=url, next_fetch_at=datetime.now(timezone.utc),
        ).returning(CrawlTarget.id))
    state = SimpleNamespace(factory=factory, source_id=source_id, target_id=target_id, url=url, tag=tag)
    state.document_id, state.updated_at = await crawl(state, "first version")
    try:
        yield state
    finally:
        async with factory() as session, session.begin():
            await session.execute(delete(Document).where(Document.source_id == source_id))
            await session.execute(delete(CrawlTarget).where(CrawlTarget.id == target_id))
            await session.execute(delete(Source).where(Source.id == source_id))
            await session.execute(delete(VocabularyChange).where(VocabularyChange.added.contains([tag])))
        await engine.dispose()


def page(db, body):
    return ProcessedDocument(url=db.url, canonical_url=db.url, document_type="article", title="Title",
                             description=None, body=body, author=None, content_hash=f"hash-{body}")


async def write_document(session, db, body):
    document_id = await upsert_document(session, page(db, body), source_id=db.source_id, crawl_target_id=db.target_id)
    return document_id, await session.scalar(select(Document.updated_at).where(Document.id == document_id))


async def crawl(db, body):
    async with db.factory() as session, session.begin():
        return await write_document(session, db, body)


def index(db, source_updated_at=None):
    vector = func.to_tsvector("simple", literal(db.tag))
    vectors = SearchVectors(document_id=db.document_id, source_id=db.source_id,
                            source_updated_at=source_updated_at or db.updated_at,
                            text_vector=vector, code_vector=func.to_tsvector("simple", literal("")))
    return persist_search_vectors(db.factory, vectors, indexed_hash=HASH)


async def is_current(db):
    async with db.factory() as session:
        return await is_index_current(session, db.document_id, config=CONFIG)


async def has_index_row(db):
    async with db.factory() as session:
        return await session.get(SearchIndex, db.document_id) is not None


async def test_index_write_waiting_on_a_crawl_is_rejected_as_stale(db):
    async with db.factory() as crawler, crawler.begin():
        await write_document(crawler, db, "second version")
        waiting = asyncio.create_task(index(db))
        await asyncio.sleep(0.3)
        assert not waiting.done(), "the writer must wait for the crawler's row lock"
    assert await waiting is IndexStatus.STALE
    assert not await has_index_row(db)


async def test_crawl_after_an_index_write_makes_the_index_outdated(db):
    assert await index(db) is IndexStatus.INDEXED
    assert await is_current(db)
    await crawl(db, "second version")
    assert not await is_current(db)


async def test_crawl_transaction_older_than_the_index_write_is_still_seen(db):
    """updated_at must be taken at the write, not when the crawl transaction began."""
    async with db.factory() as crawler, crawler.begin():
        await crawler.execute(select(func.now()))
        await asyncio.sleep(0.05)
        assert await index(db) is IndexStatus.INDEXED
        await write_document(crawler, db, "second version")
    assert not await is_current(db)


async def test_recrawl_with_no_change_does_not_invalidate_an_index_write(db):
    await crawl(db, "first version")
    assert await index(db) is IndexStatus.INDEXED
    assert await is_current(db)


async def test_two_indexers_write_once_and_count_the_vocabulary_once(db):
    results = await asyncio.gather(index(db), index(db))
    assert sorted(result.value for result in results) == sorted(
        [IndexStatus.INDEXED.value, IndexStatus.UNCHANGED.value])
    async with db.factory() as session:
        changes = await session.scalar(select(func.count(VocabularyChange.id)).where(VocabularyChange.added.contains([db.tag])))
    assert changes == 1
