"""Sitemap discovery and worker dispatch without live network or database writes."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from crawler.frontier.scope import CrawlScope
from crawler.parser.sitemap import extract_robots_sitemaps, parse_sitemap_resource
from crawler.policy_and_politeness.policy_coordinator import FetchResult
from crawler.policy_and_politeness.robots_policy import RobotsDecision, _decision_for_status
from crawler.seed.discovery import build_initial_targets
from crawler.worker.jobs import jobs
from crawler.worker.jobs.utility import _create_discovered_targets


def source(config=None):
    return SimpleNamespace(id=1, base_url="https://example.com/docs", kind="website",
        allowed_hosts=["example.com"], config=config or {})


def test_seed_configuration_host_filter_and_default_sitemap():
    values = build_initial_targets(source({"sitemap_urls": ["https://example.com/custom.xml", "https://evil.test/map.xml"]}))
    assert [(v.kind, v.fetch_url) for v in values] == [
        ("page", "https://example.com/docs"), ("sitemap", "https://example.com/custom.xml"), ("sitemap", "https://example.com/sitemap.xml")]
    assert len(build_initial_targets(source({"discover_sitemaps": False}))) == 1
    assert build_initial_targets(source({"allowed_path_prefixes": ["/other"]}))[0].kind == "sitemap"


def test_gzip_file_mime_types_are_only_enabled_for_sitemap_jobs():
    assert jobs._resource_fetcher("sitemap").config.permits_media_type("application/gzip")
    assert jobs._resource_fetcher("sitemap").config.permits_media_type("application/octet-stream")
    assert not jobs._resource_fetcher("page").config.permits_media_type("application/gzip")


def test_robots_declarations_are_absolute_bounded_and_case_insensitive():
    raw = "Sitemap: https://example.com/a.xml\nsitemap: https://example.com/a.xml # comment\nSitemap: /relative\nSitemap: file:///tmp/map\n"
    assert extract_robots_sitemaps(raw) == ("https://example.com/a.xml",)
    assert len(extract_robots_sitemaps("\n".join(f"Sitemap: https://example.com/{n}" for n in range(200)))) == 100
    result = _decision_for_status(url="https://example.com/docs", origin="https://example.com", status=200, content=raw, user_agent="DevelopersEyeBot")
    assert result.sitemap_urls == ("https://example.com/a.xml",)


def targets(xml, depth=0):
    parsed = parse_sitemap_resource(url="https://example.com/map.xml", content=xml, content_type="application/xml")
    return _create_discovered_targets(parsed, target_id=5, source_id=1, allowed_hosts=("example.com",),
        max_links=20, parent_depth=depth, target_kind="sitemap", scope=CrawlScope(max_depth=1, allowed_path_prefixes=("/docs",)))


def test_nested_maps_and_page_scope_have_separate_depth_meanings():
    pages = targets(b"<urlset><url><loc>https://example.com/docs/a</loc></url><url><loc>https://example.com/private</loc></url><url><loc>https://evil.test/docs/a</loc></url></urlset>", depth=1)
    assert [(v.kind, v.depth, v.discovered_from_id) for v in pages] == [("page", 0, 5)]
    index = b"<sitemapindex><sitemap><loc>https://example.com/nested.xml</loc></sitemap></sitemapindex>"
    assert targets(index)[0].kind == "sitemap"
    assert targets(index, depth=1) == []


def test_worker_sitemap_uses_policy_then_normal_finalization(monkeypatch):
    async def run():
        now = datetime.now(timezone.utc)
        target = SimpleNamespace(id=1, source_id=1, fetch_url="https://example.com/sitemap.xml", state="leased",
            lease_until=now + timedelta(minutes=5), kind="sitemap", depth=0)
        class Session:
            results = iter([target, now])
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            @asynccontextmanager
            async def begin(self): yield self
            async def scalar(self, query): return next(self.results)
            async def get(self, cls, id):
                return SimpleNamespace(is_enabled=True, allowed_hosts=["example.com"], crawl_interval_seconds=60,
                    config={"allowed_path_prefixes": ["/docs"]})
        fetch = AsyncMock(return_value=FetchResult(RobotsDecision.ALLOW, "Fetched", target.fetch_url, target.fetch_url,
            status_code=200, headers={"content-type": "application/xml"},
            body=b"<urlset><url><loc>https://example.com/docs/a</loc></url></urlset>"))
        final = AsyncMock()
        monkeypatch.setattr(jobs.PolicyCoordinator, "fetch", fetch)
        monkeypatch.setattr(jobs, "start_attempt", AsyncMock(return_value=11))
        monkeypatch.setattr(jobs, "checkpoint", AsyncMock())
        monkeypatch.setattr(jobs, "_finalize", final)
        await jobs.process_job(target, politeness_manager=object(), session_factory=Session)
        fetch.assert_awaited_once()
        result = final.call_args.kwargs
        assert result["outcome"] == "success"
        assert result["processed"].documents == ()
        assert result["targets"][0].fetch_url == "https://example.com/docs/a"
        assert result["targets"][0].depth == 0
    asyncio.run(run())
