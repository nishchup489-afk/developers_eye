import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from backend.schema.crawler_frontier import CrawlTargetCreate
from crawler.frontier.repository import enqueue_targets
from crawler.frontier.scope import CrawlScope
from crawler.parser.schemas import DiscoveredLink, ParseResult
from crawler.worker.jobs.utility import _create_discovered_targets


def test_depth_boundary_and_child_depth():
    parsed = ParseResult(source_url='https://example.com/docs', content_type='text/html', documents=(),
                         discovered_links=(DiscoveredLink(url='https://example.com/docs/child'),))
    kwargs = dict(target_id=1, source_id=1, allowed_hosts=('example.com',), max_links=1000, scope=CrawlScope(max_depth=3))
    assert _create_discovered_targets(parsed, parent_depth=3, **kwargs) == []
    assert _create_discovered_targets(parsed, parent_depth=2, **kwargs)[0].depth == 3


@pytest.mark.parametrize('path,allowed', [('/docs', True), ('/docs/python', True), ('/docstrings', False),
    ('/archive', False), ('/docs/../archive', False), ('/docs/%2e%2e/archive', False)])
def test_explicit_path_scope(path, allowed):
    scope = CrawlScope.from_config({'allowed_path_prefixes': ['/docs/']})
    assert scope.allows('https://example.com' + path, 1) is allowed


@pytest.mark.parametrize('config', [{'max_depth': -1}, {'max_depth': True}, {'max_depth': 101},
    {'max_pages': 0}, {'max_pages': '100'}, {'allowed_path_prefixes': []}, {'allowed_path_prefixes': 'docs'}])
def test_invalid_limits_rejected(config):
    with pytest.raises(ValueError):
        CrawlScope.from_config(config)


def test_duplicate_urls_do_not_use_remaining_budget_and_lock_precedes_count():
    class Session:
        def __init__(self): self.calls = []; self.inserted = []
        async def execute(self, statement):
            sql = str(statement.compile(dialect=postgresql.dialect()))
            self.calls.append(sql)
            if sql.startswith('INSERT'):
                self.inserted = [value for key, value in statement.compile().params.items() if key.startswith('normalized_url')]
                return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [42]))
        async def scalar(self, statement):
            if 'source.config' in str(statement): return {'max_pages': 10}
            self.calls.append('COUNT')
            return 9
        async def scalars(self, statement): return SimpleNamespace(all=lambda: ['https://example.com/a'])
    session = Session()
    targets = [CrawlTargetCreate(source_id=1, fetch_url='https://example.com/' + p, normalized_url='https://example.com/' + p)
               for p in ['c', 'a', 'b', 'b']]
    assert asyncio.run(enqueue_targets(session, targets, max_pages=10)) == 1
    assert 'pg_advisory_xact_lock' in session.calls[0]
    assert session.calls[1] == 'COUNT'
    assert session.inserted == ['https://example.com/b']


def test_full_source_does_not_insert_more_urls():
    class Session:
        async def execute(self, statement): assert 'pg_advisory_xact_lock' in str(statement)
        async def scalar(self, statement): return {'max_pages': 10} if 'source.config' in str(statement) else 10
    target = CrawlTargetCreate(source_id=1, fetch_url='https://example.com', normalized_url='https://example.com/')
    assert asyncio.run(enqueue_targets(Session(), [target], max_pages=10)) == 0
