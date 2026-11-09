"""One document through the whole index lifecycle on real PostgreSQL. Needs TEST_DATABASE_URL (migrated)."""
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import os

import pytest
import pytest_asyncio
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.search_terms import SearchTerm, VocabularyChange
from backend.models.source import Source
from crawler.processing import ProcessedDocument
from crawler.writer.documents import upsert_document
from indexer.config import IndexerConfig
from indexer.schemas import IndexCandidate, IndexStatus
from indexer.service import index_candidate, remove_candidate
from indexer.vocabulary import drain_vocabulary_changes
from indexer.vocabulary_rebuild import rebuild_vocabulary

CONFIG = IndexerConfig()


def word():
    # Letters only, so the vocabulary filter keeps it as a term. Ending in x
    # keeps the English stemmer from changing it into a different lexeme.
    return "".join(chr(97 + int(c, 16)) for c in uuid4().hex[:14]) + "x"


@pytest_asyncio.fixture
async def db():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw or "test" not in (make_url(raw).database or ""):
        pytest.skip("Set TEST_DATABASE_URL to a migrated PostgreSQL database with test in its name")
    engine = create_async_engine(raw)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tag = word()
    url = f"https://example.com/{tag}"
    async with factory() as session, session.begin():
        source_id = await session.scalar(insert(Source).values(
            slug=f"lifecycle-{tag}", name="Lifecycle test", kind="website", base_url="https://example.com/",
            allowed_hosts=["example.com"], crawl_interval_seconds=3600, is_enabled=True, config={},
        ).returning(Source.id))
        target_id = await session.scalar(insert(CrawlTarget).values(
            source_id=source_id, fetch_url=url, normalized_url=url, next_fetch_at=datetime.now(timezone.utc),
        ).returning(CrawlTarget.id))
    try:
        yield factory, source_id, target_id, url
    finally:
        async with factory() as session, session.begin():
            await session.execute(delete(Document).where(Document.source_id == source_id))
            await session.execute(delete(CrawlTarget).where(CrawlTarget.id == target_id))
            await session.execute(delete(Source).where(Source.id == source_id))
        await drain_vocabulary_changes(factory)
        await engine.dispose()


async def crawl(db, term):
    factory, source_id, target_id, url = db
    body = f"{term} guide for developers with enough ordinary words to be analyzed properly."
    document = ProcessedDocument(url=url, canonical_url=url, document_type="article", title="Lifecycle guide",
                                 description=None, body=body, author=None,
                                 content_hash=hashlib.sha256(body.encode()).hexdigest())
    async with factory() as session, session.begin():
        document_id = await upsert_document(session, document, source_id=source_id, crawl_target_id=target_id)
    async with factory() as session:
        updated_at = await session.scalar(select(Document.updated_at).where(Document.id == document_id))
    return IndexCandidate(document_id=document_id, source_updated_at=updated_at)


async def frequency(factory, term):
    await drain_vocabulary_changes(factory)
    async with factory() as session:
        return await session.scalar(select(SearchTerm.document_frequency).where(SearchTerm.term == term))


async def test_unchanged_update_removal_and_rebuild_keep_index_and_vocabulary_true(db):
    factory, *_ = db
    first, second = word(), word()

    candidate = await crawl(db, first)
    assert (await index_candidate(factory, candidate, config=CONFIG)).status is IndexStatus.INDEXED
    assert await frequency(factory, first) == 1

    # Same content: no new index write and no double count.
    again = await crawl(db, first)
    assert again.source_updated_at == candidate.source_updated_at
    assert (await index_candidate(factory, again, config=CONFIG)).status is IndexStatus.UNCHANGED
    assert await frequency(factory, first) == 1

    # Changed content moves the count from the old word to the new one.
    changed = await crawl(db, second)
    assert changed.source_updated_at > candidate.source_updated_at
    assert (await index_candidate(factory, changed, config=CONFIG)).status is IndexStatus.INDEXED
    assert await frequency(factory, first) is None
    assert await frequency(factory, second) == 1

    # A rebuild from the index agrees with the incremental counts.
    await rebuild_vocabulary(factory)
    assert await frequency(factory, second) == 1

    # Removal takes the index row and its count, and a rebuild does not restore them.
    async with factory() as session, session.begin():
        await session.execute(update(Document).where(Document.id == changed.document_id).values(
            is_available=False, unavailable_http_status=404, unavailable_at=datetime.now(timezone.utc)))
    assert (await remove_candidate(factory, changed.document_id)).status is IndexStatus.REMOVED
    async with factory() as session:
        assert await session.get(SearchIndex, changed.document_id) is None
    assert await frequency(factory, second) is None
    await rebuild_vocabulary(factory)
    assert await frequency(factory, second) is None
    async with factory() as session:
        assert await session.scalar(select(VocabularyChange).limit(1)) is None
