import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from crawler.worker.jobs import utility
from crawler.writer.documents import upsert_document
from crawler.parser.schemas import ParsedDocument
from crawler.processing.processing import process_document


@pytest.mark.parametrize('status', [404, 410])
def test_missing_pages_are_retained_as_unavailable_and_removed_from_search(monkeypatch, status):
    now = datetime.now(timezone.utc)
    lease = now + timedelta(minutes=5)
    target = SimpleNamespace(source_id=1, state='leased', lease_until=lease)
    class Session:
        def __init__(self): self.values = iter([target, now, True]); self.statements = []
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        @asynccontextmanager
        async def begin(self): yield self
        async def scalar(self, query): return next(self.values)
        async def scalars(self, query):
            self.statements.append(query)
            return SimpleNamespace(all=lambda: [42])
        async def execute(self, query): self.statements.append(query)
        def add(self, item): pass
    session = Session()
    complete = AsyncMock(return_value=True)
    monkeypatch.setattr(utility, 'complete_target', complete)
    monkeypatch.setattr(utility, 'finish_attempt', AsyncMock(return_value=True))
    asyncio.run(utility._finalize(session_factory=lambda: session, target_id=1, source_id=1,
        expected_lease_until=lease, attempt_id=11, action='complete', outcome='failed', message='Unavailable',
        http_status=status, body_bytes=0, retry_after_seconds=None, interval_seconds=86400,
        parsed=None, processed=None, targets=[], elapsed=.1))
    sql = [str(query.compile(dialect=postgresql.dialect())) for query in session.statements]
    assert any('UPDATE document SET' in query and 'last_crawl_target_id =' in query for query in sql)
    assert any('DELETE FROM search_index' in query for query in sql)
    assert not any('DELETE FROM document' in query for query in sql)
    complete.assert_awaited_once()


def test_successful_observation_restores_document_availability():
    document = process_document(ParsedDocument(url='https://example.com/docs', title='Python', body='Useful Python documentation.'))
    statements = []
    class Session:
        async def scalar(self, query): statements.append(query); return 42
    assert asyncio.run(upsert_document(Session(), document, source_id=1, crawl_target_id=1)) == 42
    sql = str(statements[0].compile(dialect=postgresql.dialect()))
    assert 'is_available =' in sql and 'unavailable_at =' in sql and 'unavailable_http_status =' in sql
