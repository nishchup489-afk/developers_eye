"""Run real parser/processor dispatch, intercepting network and persistence."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from crawler.policy_and_politeness.policy_coordinator import FetchResult
from crawler.policy_and_politeness.robots_policy import RobotsDecision
from crawler.seed.discovery import build_initial_targets
from crawler.worker.jobs import jobs


async def run_resource(monkeypatch, kind, body, config=None, headers=None):
    now = datetime.now(timezone.utc)
    target = SimpleNamespace(id=1, source_id=1, fetch_url="https://example.com/endpoint", state="leased",
        lease_until=now + timedelta(minutes=5), kind=kind, depth=0)
    class Session:
        results = iter([target, now])
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        @asynccontextmanager
        async def begin(self): yield self
        async def scalar(self, query): return next(self.results)
        async def get(self, cls, id):
            return SimpleNamespace(is_enabled=True, allowed_hosts=["example.com"], crawl_interval_seconds=60,
                config={"allowed_path_prefixes": ["/docs"], **(config or {})})
    fetch = AsyncMock(return_value=FetchResult(RobotsDecision.ALLOW, "Fetched", target.fetch_url, target.fetch_url,
        status_code=200, headers=headers or {"content-type": "application/xml"}, body=body))
    final = AsyncMock()
    monkeypatch.setattr(jobs.PolicyCoordinator, "fetch", fetch)
    monkeypatch.setattr(jobs, "start_attempt", AsyncMock(return_value=11))
    monkeypatch.setattr(jobs, "checkpoint", AsyncMock())
    monkeypatch.setattr(jobs, "_finalize", final)
    await jobs.process_job(target, politeness_manager=object(), session_factory=Session)
    fetch.assert_awaited_once()
    return final.call_args.kwargs


FEED = b'''<rss xmlns:atom="http://www.w3.org/2005/Atom"><channel><atom:link rel="next" href="/endpoint?page=2"/>
<item><link>/docs/a</link><title>Python guide</title><description>Useful Python programming content.</description></item>
<item><link>/private</link><description>Out of scope</description></item>
<item><link>https://evil.test/docs/a</link><description>Wrong host</description></item></channel></rss>'''


@pytest.mark.parametrize("follow", [False, True])
def test_rss_worker_stores_only_in_scope_content_and_queues_pagination(monkeypatch, follow):
    result = asyncio.run(run_resource(monkeypatch, "rss", FEED, {"follow_entry_links": follow}))
    assert result["outcome"] == "success"
    assert [d.url for d in result["processed"].documents] == ["https://example.com/docs/a"]
    assert [t.kind for t in result["targets"]] == (["page", "rss"] if follow else ["rss"])


def test_rss_http_directives_and_malformed_feed(monkeypatch):
    result = asyncio.run(run_resource(monkeypatch, "rss", FEED,
        headers={"content-type": "application/rss+xml", "x-robots-tag": "noindex, nofollow"}))
    assert result["processed"].documents == ()
    assert result["processed"].skipped[0].reason == "noindex"
    assert result["targets"] == []
    failed = asyncio.run(run_resource(monkeypatch, "rss", b"<rss>"))
    assert failed["action"] == "retry"
    assert failed["measurements"]["error_category"] == "parse"


def test_rss_source_queues_collection_outside_content_path():
    source = SimpleNamespace(id=1, kind="rss", base_url="https://example.com/feed.xml", allowed_hosts=["example.com"], config={"allowed_path_prefixes": ["/docs"]})
    target, = build_initial_targets(source)
    assert target.kind == "rss"
