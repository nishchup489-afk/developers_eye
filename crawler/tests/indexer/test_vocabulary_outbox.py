"""Vocabulary outbox on real PostgreSQL. Needs TEST_DATABASE_URL (migrated)."""
import asyncio
import os
from random import choices
from string import ascii_lowercase

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.search_terms import SearchTerm, VocabularyChange
from indexer.vocabulary import (
    drain_vocabulary_changes,
    lock_vocabulary,
    synchronize_vocabulary,
)


@pytest_asyncio.fixture
async def factory():
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test database")
    if "test" not in (make_url(raw).database or "").lower():
        pytest.fail("TEST_DATABASE_URL must point at a test database")
    engine = create_async_engine(raw)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        await session.execute(delete(VocabularyChange))
    yield sessions
    async with sessions() as session, session.begin():
        await session.execute(delete(VocabularyChange))
        await session.execute(delete(SearchTerm).where(SearchTerm.term.like("zq%")))
    await engine.dispose()


def term():
    return "zq" + "".join(choices(ascii_lowercase, k=12))


async def record(sessions, old=(), new=()):
    async with sessions() as session, session.begin():
        await synchronize_vocabulary(session, old_lexemes=old, new_lexemes=new)


async def frequency(sessions, word):
    async with sessions() as session:
        return await session.scalar(select(SearchTerm.document_frequency).where(SearchTerm.term == word))


async def test_concurrent_writers_never_lose_a_count(factory):
    shared = term()
    await asyncio.gather(*(record(factory, new=[shared]) for _ in range(40)))
    assert await drain_vocabulary_changes(factory) == 40
    assert await frequency(factory, shared) == 40


async def test_removal_decrements_then_deletes_at_zero(factory):
    word = term()
    await record(factory, new=[word])
    await record(factory, new=[word])
    await drain_vocabulary_changes(factory)
    await record(factory, old=[word])
    await drain_vocabulary_changes(factory)
    assert await frequency(factory, word) == 1
    await record(factory, old=[word])
    await drain_vocabulary_changes(factory)
    assert await frequency(factory, word) is None


async def test_add_and_remove_in_one_batch_cancel_out(factory):
    word = term()
    await record(factory, new=[word])
    await record(factory, old=[word])
    await drain_vocabulary_changes(factory)
    assert await frequency(factory, word) is None


async def test_rolled_back_write_queues_nothing(factory):
    word = term()
    with pytest.raises(RuntimeError):
        async with factory() as session, session.begin():
            await synchronize_vocabulary(session, old_lexemes=(), new_lexemes=[word])
            raise RuntimeError("index write failed")
    assert await drain_vocabulary_changes(factory) == 0
    assert await frequency(factory, word) is None


async def test_large_backlog_drains_across_batches_and_empties_the_queue(factory):
    word = term()
    for _ in range(5):
        await record(factory, new=[word])
    assert await drain_vocabulary_changes(factory, batch_size=2) == 5
    assert await frequency(factory, word) == 5
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(VocabularyChange)) == 0


async def test_second_drainer_steps_aside_and_loses_nothing(factory):
    word = term()
    await record(factory, new=[word])
    async with factory() as session, session.begin():
        await lock_vocabulary(session)
        assert await drain_vocabulary_changes(factory) == 0
    assert await drain_vocabulary_changes(factory) == 1
    assert await frequency(factory, word) == 1
