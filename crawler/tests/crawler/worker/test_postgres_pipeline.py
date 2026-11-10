"""Dedicated PostgreSQL regression tests; never use the crawler's live database."""
import asyncio
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.crawl_attempt import CrawlAttempt
from backend.models.crawl_host import CrawlHost
from backend.models.crawl_monitor import CrawlEvent
from backend.models.crawler_frontier import CrawlTarget
from backend.models.documents import Document
from backend.models.search_index import SearchIndex
from backend.models.source import Source
from backend.schema.crawler_frontier import CrawlTargetCreate, CrawlTargetRead
from backend.admin_services.crawler_monitoring import build_monitor, inspect_document
from crawler.frontier.repository import enqueue_targets
from crawler.policy_and_politeness.policy_coordinator import FetchResult, PolicyCoordinator
from crawler.policy_and_politeness.politeness_policy import PolitenessManager
from crawler.policy_and_politeness.robots_policy import RobotsDecision
from crawler.scheduler.repository import claim_targets, recover_expired_leases
from crawler.worker.jobs.jobs import process_job
from crawler.worker.recovery import recover_failed_claim
from crawler.writer.attempts import start_attempt
from indexer.config import IndexerConfig
from indexer.selector import (
    select_index_candidates,
    select_removal_candidates,
)
from indexer.service import remove_candidate
from indexer.schemas import IndexStatus
from sqlalchemy import text

import crawler.policy_and_politeness.policy_coordinator as policy_module

from crawler.fetcher.schemas import OneHopResponse
from crawler.policy_and_politeness.robots_policy import RobotsPolicyResult
from crawler.policy_and_politeness.shared_politeness import SharedPolitenessManager



def test_http_429_retry_after_persists_and_delays_reclaim(monkeypatch):
    retry_after_seconds = 180
    host = "example.com"

    html = (
        b"<html><head><title>Python Documentation</title></head>"
        b"<body><main>Useful Python documentation with code "
        b"examples and programming guides.</main></body></html>"
    )

    class ScriptedFetcher:
        def __init__(self):
            self.calls = []

        async def fetch_once(
            self,
            *,
            url,
            approved_ips,
            max_body_bytes,
            timeout_seconds,
            user_agent,
        ):
            self.calls.append(url)

            if len(self.calls) == 1:
                return OneHopResponse(
                    429,
                    {"Retry-After": str(retry_after_seconds)},
                )

            return OneHopResponse(
                200,
                {"Content-Type": "text/html"},
                html,
            )

    async def resolve_dns(hostname):
        assert hostname == host
        return ["93.184.215.14"]

    async def allow_robots(session, url, fetcher, *, user_agent):
        return RobotsPolicyResult(
            RobotsDecision.ALLOW,
            "Allowed by test policy",
            f"https://{host}",
        )

    monkeypatch.setattr(
        policy_module,
        "resolve_safe_destination",
        resolve_dns,
    )
    monkeypatch.setattr(
        policy_module,
        "evaluate_robots_policy",
        allow_robots,
    )

    async def run():
        async with database() as (factory, source_id):
            fetcher = ScriptedFetcher()

            manager = SharedPolitenessManager(
                factory,
                min_interval_seconds=0,
                max_concurrent_per_host=1,
                max_backoff_seconds=300,
                max_wait_seconds=2,
                hold_seconds=5,
            )

            async def try_claim():
                async with factory() as session:
                    async with session.begin():
                        rows = await claim_targets(
                            session,
                            limit=1,
                            source_id=source_id,
                            host_hold_seconds=0,
                        )
                        return [
                            CrawlTargetRead.model_validate(row)
                            for row in rows
                        ]

            try:
                await seed(factory, source_id, 1)

                # Isolate this test from existing host backoff.
                async with factory() as session, session.begin():
                    await session.execute(
                        update(CrawlHost)
                        .where(CrawlHost.host == host)
                        .values(
                            next_allowed_at=func.clock_timestamp(),
                            backoff_until=None,
                        )
                    )

                # 1. First request receives HTTP 429.
                claimed = await try_claim()
                assert len(claimed) == 1
                target_id = claimed[0].id

                result = await process_job(
                    claimed[0],
                    session_factory=factory,
                    politeness_manager=manager,
                    fetcher=fetcher,
                )

                assert result.outcome == "failed"
                assert result.http_status == 429
                assert len(fetcher.calls) == 1

                # 2. Verify persisted retry scheduling.
                async with factory() as session:
                    target = await session.get(CrawlTarget, target_id)
                    host_state = await session.get(CrawlHost, host)
                    now = await session.scalar(
                        select(func.clock_timestamp())
                    )

                    assert target.state == "queued"
                    assert target.lease_until is None
                    assert target.failure_count == 1

                    target_wait = (
                        target.next_fetch_at - now
                    ).total_seconds()

                    host_wait = (
                        host_state.backoff_until - now
                    ).total_seconds()

                    # 180-second Retry-After overrides
                    # the default 60-second failure delay.
                    assert 170 <= target_wait <= 180
                    assert 170 <= host_wait <= 180

                # 3. The scheduler must refuse early reclaim.
                assert await try_claim() == []
                assert len(fetcher.calls) == 1

                # 4. Simulate passage of the retry period.
                # No need to sleep for three minutes.
                async with factory() as session, session.begin():
                    past = (
                        func.clock_timestamp()
                        - text("interval '1 second'")
                    )

                    await session.execute(
                        update(CrawlTarget)
                        .where(CrawlTarget.id == target_id)
                        .values(next_fetch_at=past)
                    )

                    await session.execute(
                        update(CrawlHost)
                        .where(CrawlHost.host == host)
                        .values(
                            next_allowed_at=past,
                            backoff_until=past,
                        )
                    )

                # 5. The same target becomes claimable again.
                claimed = await try_claim()
                assert len(claimed) == 1
                assert claimed[0].id == target_id

                # Second request returns HTTP 200.
                result = await process_job(
                    claimed[0],
                    session_factory=factory,
                    politeness_manager=manager,
                    fetcher=fetcher,
                )

                assert result.outcome == "success"
                assert result.http_status == 200
                assert len(fetcher.calls) == 2

                # 6. Successful retry resets failure state.
                async with factory() as session:
                    target = await session.get(CrawlTarget, target_id)

                    assert target.state == "queued"
                    assert target.lease_until is None
                    assert target.failure_count == 0

                    attempts = await session.scalar(
                        select(func.count(CrawlAttempt.id))
                        .where(CrawlAttempt.crawl_target_id == target_id)
                    )
                    assert attempts == 2

            finally:
                # Leave the shared test host ready for other tests.
                async with factory() as session, session.begin():
                    await session.execute(
                        update(CrawlHost)
                        .where(CrawlHost.host == host)
                        .values(
                            next_allowed_at=func.clock_timestamp(),
                            backoff_until=None,
                        )
                    )

    asyncio.run(run())

@asynccontextmanager
async def database():
    raw = os.environ.get('TEST_DATABASE_URL')
    if not raw:
        pytest.skip('Set TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test database')
    url = make_url(raw)
    if url.drivername != 'postgresql+asyncpg' or not url.database or 'test' not in url.database.lower():
        pytest.fail('TEST_DATABASE_URL must be PostgreSQL+asyncpg with test in the database name')
    engine = create_async_engine(raw, connect_args={'timeout': 5, 'command_timeout': 15})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source_id = None
    try:
        async with factory() as session, session.begin():
            source = Source(slug='regression-' + uuid4().hex, name='Regression test', kind='website',
                base_url='https://example.com/docs', allowed_hosts=['example.com'],
                crawl_interval_seconds=60, is_enabled=True, config={'max_depth': 3, 'max_pages': 7})
            session.add(source)
            await session.flush()
            source_id = source.id
        yield factory, source_id
    finally:
        if source_id is not None:
            async with factory() as session, session.begin():
                ids = select(CrawlTarget.id).where(CrawlTarget.source_id == source_id)
                await session.execute(delete(Document).where(Document.source_id == source_id))
                await session.execute(delete(CrawlAttempt).where(CrawlAttempt.crawl_target_id.in_(ids)))
                await session.execute(delete(CrawlTarget).where(CrawlTarget.source_id == source_id))
                await session.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


async def seed(factory, source_id, count):
    async with factory() as session, session.begin():
        await enqueue_targets(session, [CrawlTargetCreate(source_id=source_id,
            fetch_url=f'https://example.com/docs/{i}', normalized_url=f'https://example.com/docs/{i}') for i in range(count)])


async def claim(factory, source_id, count=1):
    """Claim several targets of one host; production takes one per host per gap."""
    async with factory() as session, session.begin():
        await session.execute(update(CrawlHost).values(next_allowed_at=func.now(), backoff_until=None))
        targets = []
        for _ in range(count):
            targets += await claim_targets(session, limit=1, source_id=source_id, host_hold_seconds=0)
        await asyncio.sleep(.01)
        return [CrawlTargetRead.model_validate(target) for target in targets]


@pytest.mark.parametrize("kind", ["sitemap", "rss", "api"])
def test_structured_resources_commit_documents_targets_and_attempts(monkeypatch, kind):
    bodies = {
        "sitemap": b"<urlset><url><loc>https://example.com/docs/imported</loc></url></urlset>",
        "rss": b'<rss xmlns:atom="http://www.w3.org/2005/Atom"><channel><atom:link rel="next" href="https://example.com/endpoint?page=2"/><item><link>https://example.com/docs/imported</link><title>Python guide</title><description>Useful Python programming documentation.</description></item></channel></rss>',
        "api": json.dumps({"items": [{"url": "https://example.com/docs/imported", "title": "Python guide", "body": "Useful Python programming documentation."}], "next": "https://example.com/endpoint?page=2"}).encode(),
    }
    async def fetch(self, session, url):
        return FetchResult(RobotsDecision.ALLOW, "Fetched", url, url, status_code=200,
            headers={"content-type": "application/json" if kind == "api" else "application/xml"}, body=bodies[kind])
    monkeypatch.setattr(PolicyCoordinator, "fetch", fetch)
    async def run():
        async with database() as (factory, source_id):
            async with factory() as session, session.begin():
                await session.execute(update(Source).where(Source.id == source_id).values(
                    config={"max_depth": 3, "max_pages": 7, "api": {"next_path": "next"}}))
                await enqueue_targets(session, [CrawlTargetCreate(source_id=source_id, kind=kind,
                    fetch_url="https://example.com/endpoint", normalized_url="https://example.com/endpoint")])
            target, = await claim(factory, source_id)
            result = await process_job(target, session_factory=factory, politeness_manager=PolitenessManager(min_interval_seconds=0))
            assert result.outcome == "success"
            assert result.links_enqueued == 1
            assert result.documents_saved == (0 if kind == "sitemap" else 1)
            async with factory() as session:
                attempt = await session.get(CrawlAttempt, result.attempt_id)
                assert attempt.finished_at is not None and attempt.outcome == "success"
                assert attempt.telemetry["resource_kind"] == kind
                child, = (await session.scalars(select(CrawlTarget).where(CrawlTarget.discovered_from_id == target.id))).all()
                assert child.kind == ("page" if kind == "sitemap" else kind)
                assert child.depth == (0 if kind == "sitemap" else 1)
                documents = (await session.scalars(select(Document).where(Document.source_id == source_id))).all()
                assert len(documents) == result.documents_saved
                if documents:
                    assert documents[0].canonical_url == "https://example.com/docs/imported"
                    assert documents[0].metadata_["ingestion_format"] == ("rss" if kind == "rss" else "json_api")
                    inspected = await inspect_document(session, document_id=documents[0].id)
                    assert inspected is not None
    asyncio.run(run())


def install_fetch(monkeypatch, statuses=None):
    statuses = iter(statuses) if statuses else None
    async def fetch(self, session, url):
        status = next(statuses) if statuses else 200
        html = f'<html><head><title>Python {url}</title></head><body><main>Useful Python documentation with code examples.</main><a href="/linked/a">A</a><a href="/linked/b">B</a><a href="/linked/c">C</a><a href="/linked/d">D</a></body></html>'
        return FetchResult(RobotsDecision.ALLOW, f'Fetched HTTP {status}', url, url,
            status_code=status, headers={'content-type': 'text/html'}, body=html.encode() if status == 200 else b'')
    monkeypatch.setattr(PolicyCoordinator, 'fetch', fetch)


def test_concurrent_claims_atomic_writes_and_shared_source_budget(monkeypatch):
    install_fetch(monkeypatch)
    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 4)
            first, second = await asyncio.gather(claim(factory, source_id, 2), claim(factory, source_id, 2))
            assert len(first) == len(second) == 2
            assert {t.id for t in first}.isdisjoint(t.id for t in second)
            manager = PolitenessManager(min_interval_seconds=0)
            results = await asyncio.gather(*(process_job(t, session_factory=factory, politeness_manager=manager) for t in first + second))
            assert all(r.outcome == 'success' for r in results)
            async with factory() as session:
                assert await session.scalar(select(func.count(CrawlTarget.id)).where(CrawlTarget.source_id == source_id)) == 7
                assert await session.scalar(select(func.count(Document.id)).where(Document.source_id == source_id)) == 4
                assert await session.scalar(select(func.count(CrawlAttempt.id)).join(CrawlTarget).where(
                    CrawlTarget.source_id == source_id, CrawlAttempt.finished_at.is_(None))) == 0
                monitor = await build_monitor(session, source_id=source_id)
                assert monitor['summary']['attempted'] == monitor['summary']['persisted'] == 4
                assert len(monitor['documents']) == 4
                detail = await inspect_document(session, monitor['documents'][0]['id'])
                assert detail['body'] and detail['is_available'] is True
    asyncio.run(run())



def test_removed_page_invalidates_index_and_recovers_when_restored(monkeypatch):
    install_fetch(monkeypatch, [200, 404, 200])

    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 1)
            manager = PolitenessManager(min_interval_seconds=0)
            config = IndexerConfig()

            # 1. Initial crawl: HTTP 200
            target = (await claim(factory, source_id))[0]
            await process_job(
                target,
                session_factory=factory,
                politeness_manager=manager,
            )

            # Simulate an already-indexed document.
            async with factory() as session, session.begin():
                document = await session.scalar(
                    select(Document).where(Document.source_id == source_id)
                )
                assert document is not None
                document_id = document.id

                session.add(
                    SearchIndex(
                        document_id=document_id,
                        search_vector=func.to_tsvector("english", document.body),
                        code_vector=func.to_tsvector("simple", ""),
                        indexed_hash=document.content_hash,
                    )
                )

            # 2. Recrawl: HTTP 404
            async with factory() as session, session.begin():
                await session.execute(
                    update(CrawlTarget)
                    .where(CrawlTarget.source_id == source_id)
                    .where(CrawlTarget.id != target.id)
                    .values(next_fetch_at=func.now() + timedelta(days=1))
                )
                await session.execute(
                    update(CrawlTarget)
                    .where(CrawlTarget.id == target.id)
                    .values(next_fetch_at=func.now())
                )

            target = (await claim(factory, source_id))[0]
            await process_job(
                target,
                session_factory=factory,
                politeness_manager=manager,
            )

            # Crawler owns availability, NOT index deletion.
            async with factory() as session:
                document = await session.get(Document, document_id)
                assert document.is_available is False
                assert document.unavailable_http_status == 404

                index = await session.get(SearchIndex, document_id)
                assert index is not None

                candidates = await select_removal_candidates(
                    session,
                    config=config,
                )
                assert document_id in candidates

            # 3. Indexer owns index removal.
            result = await remove_candidate(factory, document_id)
            assert result.status is IndexStatus.REMOVED

            async with factory() as session:
                assert await session.get(SearchIndex, document_id) is None

            # 4. Recrawl: HTTP 200 (recovery)
            async with factory() as session, session.begin():
                await session.execute(
                    update(CrawlTarget)
                    .where(CrawlTarget.source_id == source_id)
                    .where(CrawlTarget.id != target.id)
                    .values(next_fetch_at=func.now() + timedelta(days=1))
                )
                await session.execute(
                    update(CrawlTarget)
                    .where(CrawlTarget.id == target.id)
                    .values(next_fetch_at=func.now())
                )

            target = (await claim(factory, source_id))[0]
            await process_job(
                target,
                session_factory=factory,
                politeness_manager=manager,
            )

            async with factory() as session:
                document = await session.get(Document, document_id)
                assert document is not None
                assert document.is_available is True
                assert document.unavailable_http_status is None

                # Recovered document needs indexing again.
                candidates = await select_index_candidates(
                    session,
                    config=config,
                )
                assert document_id in {
                    candidate.document_id for candidate in candidates
                }

                # It must no longer be a removal candidate.
                removal_candidates = await select_removal_candidates(
                    session,
                    config=config,
                )
                assert document_id not in removal_candidates

    asyncio.run(run())


def test_sitemap_past_link_limit_queues_every_url_and_rerun_adds_nothing(monkeypatch):
    total = 2_345
    entries = b"".join(b"<url><loc>https://example.com/docs/p%d</loc></url>" % i for i in range(total))
    body = b"<urlset>" + entries + b"</urlset>"

    async def fetch(self, session, url):
        return FetchResult(RobotsDecision.ALLOW, 'Fetched', url, url, status_code=200,
            headers={'content-type': 'application/xml'}, body=body)
    monkeypatch.setattr(PolicyCoordinator, 'fetch', fetch)

    async def count(factory, source_id):
        async with factory() as session:
            return await session.scalar(select(func.count(CrawlTarget.id)).where(
                CrawlTarget.source_id == source_id, CrawlTarget.kind == 'page'))

    async def run():
        async with database() as (factory, source_id):
            async with factory() as session, session.begin():
                await session.execute(update(Source).where(Source.id == source_id).values(
                    config={'max_depth': 3, 'max_pages': 10_000}))
                session.add(CrawlTarget(source_id=source_id, fetch_url='https://example.com/sitemap.xml',
                    normalized_url='https://example.com/sitemap.xml', kind='sitemap', priority=1_000_000))
            manager = PolitenessManager(min_interval_seconds=0)
            for _ in range(2):
                async with factory() as session, session.begin():
                    await session.execute(update(CrawlTarget).where(CrawlTarget.kind == 'sitemap',
                        CrawlTarget.source_id == source_id).values(next_fetch_at=func.now()))
                    await session.execute(update(CrawlTarget).where(CrawlTarget.kind == 'page',
                        CrawlTarget.source_id == source_id).values(next_fetch_at=func.now() + timedelta(days=1)))
                sitemap = (await claim(factory, source_id))[0]
                assert sitemap.kind == 'sitemap'
                result = await process_job(sitemap, session_factory=factory, politeness_manager=manager, max_links=500)
                assert result.outcome == 'success'
                assert await count(factory, source_id) == total
    asyncio.run(run())


def test_expiration_and_old_worker_recovery_do_not_touch_new_claims():
    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 2)
            targets = await claim(factory, source_id, 2)
            old_lease = datetime.now(timezone.utc) - timedelta(seconds=10)
            async with factory() as session, session.begin():
                await session.execute(update(CrawlTarget).where(CrawlTarget.id == targets[0].id).values(lease_until=old_lease))
                expired = await start_attempt(session, targets[0].id, lease_until=old_lease)
                old = await start_attempt(session, targets[1].id, lease_until=old_lease)
                active = await start_attempt(session, targets[1].id, lease_until=targets[1].lease_until)
            await recover_failed_claim(factory, targets[1].id, old_lease, 'timeout', 'Old worker timed out')
            async with factory() as session, session.begin():
                assert await recover_expired_leases(session) == 1
            async with factory() as session:
                assert (await session.get(CrawlAttempt, expired)).outcome == 'failed'
                assert (await session.get(CrawlAttempt, old)).outcome == 'failed'
                assert (await session.get(CrawlAttempt, active)).finished_at is None
                recovered = await session.get(CrawlTarget, targets[0].id)
                assert recovered.failure_count == 1 and recovered.next_fetch_at > datetime.now(timezone.utc)
                assert (await session.get(CrawlTarget, targets[1].id)).lease_until == targets[1].lease_until
    asyncio.run(run())


def _sitemap_index_xml(*urls: str) -> bytes:
    entries = "".join(f"<sitemap><loc>{url}</loc></sitemap>" for url in urls)
    return f"<sitemapindex>{entries}</sitemapindex>".encode()


def _sitemap_urlset_xml(*urls: str) -> bytes:
    entries = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    return f"<urlset>{entries}</urlset>".encode()


async def _claim_specific_url(factory, source_id: int, url: str) -> CrawlTargetRead:
    """Make one target due without accidentally claiming discovered page targets."""
    async with factory() as session, session.begin():
        await session.execute(
            update(CrawlTarget)
            .where(CrawlTarget.source_id == source_id, CrawlTarget.fetch_url != url)
            .values(next_fetch_at=func.clock_timestamp() + timedelta(days=1))
        )
        await session.execute(
            update(CrawlTarget)
            .where(CrawlTarget.source_id == source_id, CrawlTarget.fetch_url == url)
            .values(next_fetch_at=func.clock_timestamp())
        )
    targets = await claim(factory, source_id)
    assert len(targets) == 1
    assert targets[0].fetch_url == url
    return targets[0]


def test_nested_sitemap_children_are_scoped_and_idempotent(monkeypatch):
    """Parent index -> child maps -> pages, with durable deduplication on replays."""
    root = "https://example.com/sitemap.xml"
    first = "https://example.com/maps/first.xml"
    second = "https://example.com/maps/second.xml"
    documents = {
        root: _sitemap_index_xml(
            first, second, first, "https://unapproved.invalid/external.xml"
        ),
        first: _sitemap_urlset_xml(
            "https://example.com/docs/a",
            "https://example.com/docs/shared",
            "https://example.com/private",
            "https://unapproved.invalid/docs/unsafe",
        ),
        second: _sitemap_urlset_xml(
            "https://example.com/docs/b",
            "https://example.com/docs/shared",
        ),
    }

    async def fetch(self, session, url):
        assert url in documents, f"Unexpected sitemap fetch: {url}"
        return FetchResult(
            RobotsDecision.ALLOW, "Fetched", url, url,
            status_code=200, headers={"content-type": "application/xml"},
            body=documents[url],
        )

    monkeypatch.setattr(PolicyCoordinator, "fetch", fetch)

    async def run():
        async with database() as (factory, source_id):
            async with factory() as session, session.begin():
                await session.execute(
                    update(Source).where(Source.id == source_id).values(
                        config={
                            "max_depth": 1,
                            "max_pages": 32,
                            "allowed_path_prefixes": ["/docs"],
                        }
                    )
                )
                session.add(
                    CrawlTarget(
                        source_id=source_id,
                        fetch_url=root,
                        normalized_url=root,
                        kind="sitemap",
                        depth=0,
                    )
                )

            manager = PolitenessManager(min_interval_seconds=0)
            for url in (root, first, second):
                target = await _claim_specific_url(factory, source_id, url)
                result = await process_job(
                    target, session_factory=factory,
                    politeness_manager=manager, max_links=2,
                )
                assert result.outcome == "success"

            expected = {
                (root, "sitemap", 0),
                (first, "sitemap", 1),
                (second, "sitemap", 1),
                ("https://example.com/docs/a", "page", 0),
                ("https://example.com/docs/b", "page", 0),
                ("https://example.com/docs/shared", "page", 0),
            }

            async def observed():
                async with factory() as session:
                    rows = (
                        await session.execute(
                            select(
                                CrawlTarget.fetch_url,
                                CrawlTarget.kind,
                                CrawlTarget.depth,
                            ).where(CrawlTarget.source_id == source_id)
                        )
                    ).all()
                    return {tuple(row) for row in rows}

            assert await observed() == expected

            # Parent and child recrawls must not introduce duplicate rows.
            for url in (root, first, second):
                target = await _claim_specific_url(factory, source_id, url)
                result = await process_job(
                    target, session_factory=factory,
                    politeness_manager=manager, max_links=2,
                )
                assert result.outcome == "success"
            assert await observed() == expected

    asyncio.run(run())


def test_nested_sitemap_depth_limit_rejects_grandchild(monkeypatch):
    """A sitemap index at depth one must not schedule a depth-two child."""
    root = "https://example.com/sitemap.xml"
    child = "https://example.com/maps/child.xml"
    grandchild = "https://example.com/maps/grandchild.xml"
    responses = {
        root: _sitemap_index_xml(child),
        child: _sitemap_index_xml(grandchild),
    }

    async def fetch(self, session, url):
        assert url in responses, f"Unexpected fetch beyond sitemap depth limit: {url}"
        return FetchResult(
            RobotsDecision.ALLOW, "Fetched", url, url,
            status_code=200, headers={"content-type": "application/xml"},
            body=responses[url],
        )

    monkeypatch.setattr(PolicyCoordinator, "fetch", fetch)

    async def run():
        async with database() as (factory, source_id):
            async with factory() as session, session.begin():
                await session.execute(
                    update(Source).where(Source.id == source_id).values(
                        config={"max_depth": 1, "max_pages": 16}
                    )
                )
                session.add(CrawlTarget(
                    source_id=source_id, fetch_url=root,
                    normalized_url=root, kind="sitemap", depth=0,
                ))

            manager = PolitenessManager(min_interval_seconds=0)
            for url in (root, child):
                target = await _claim_specific_url(factory, source_id, url)
                result = await process_job(
                    target, session_factory=factory,
                    politeness_manager=manager,
                )
                assert result.outcome == "success"

            async with factory() as session:
                rows = (
                    await session.execute(
                        select(CrawlTarget.fetch_url, CrawlTarget.depth)
                        .where(CrawlTarget.source_id == source_id)
                    )
                ).all()
                assert {tuple(row) for row in rows} == {
                    (root, 0), (child, 1),
                }
                assert await session.scalar(
                    select(func.count(CrawlTarget.id))
                    .where(CrawlTarget.source_id == source_id, CrawlTarget.fetch_url == grandchild)
                ) == 0

    asyncio.run(run())


def test_sitemap_overflow_replay_after_partial_commit(monkeypatch):
    """A transient failure after a committed overflow batch must lose no URLs."""
    from crawler.worker.jobs import jobs as jobs_module

    root = "https://example.com/sitemap.xml"
    total = 550
    xml = _sitemap_urlset_xml(
        *(f"https://example.com/docs/p{i}" for i in range(total))
    )

    async def fetch(self, session, url):
        assert url == root
        return FetchResult(
            RobotsDecision.ALLOW, "Fetched", url, url,
            status_code=200, headers={"content-type": "application/xml"},
            body=xml,
        )

    monkeypatch.setattr(PolicyCoordinator, "fetch", fetch)

    async def run():
        async with database() as (factory, source_id):
            async with factory() as session, session.begin():
                await session.execute(
                    update(Source).where(Source.id == source_id).values(
                        config={"max_depth": 3, "max_pages": 1_000}
                    )
                )
                session.add(CrawlTarget(
                    source_id=source_id, fetch_url=root,
                    normalized_url=root, kind="sitemap", depth=0,
                ))

            manager = PolitenessManager(min_interval_seconds=0)
            original_enqueue = jobs_module.enqueue_targets
            calls = 0

            async def interrupted_enqueue(session, targets, *, max_pages):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("Injected failure after committed overflow batch")
                return await original_enqueue(
                    session, targets, max_pages=max_pages
                )

            # First batch of overflow targets commits, then the next batch fails.
            with monkeypatch.context() as patch:
                patch.setattr(jobs_module, "enqueue_targets", interrupted_enqueue)
                target = await _claim_specific_url(factory, source_id, root)
                first = await process_job(
                    target, session_factory=factory,
                    politeness_manager=manager, max_links=100,
                )
            assert first.outcome == "failed"
            assert calls == 2

            async def page_count():
                async with factory() as session:
                    return await session.scalar(
                        select(func.count(CrawlTarget.id)).where(
                            CrawlTarget.source_id == source_id,
                            CrawlTarget.kind == "page",
                        )
                    )

            assert await page_count() == 100
            async with factory() as session:
                failed_target = await session.get(CrawlTarget, target.id)
                assert failed_target.state == "queued"
                assert failed_target.failure_count == 1

            # A later attempt rereads the sitemap rather than using a cursor.
            # The frontier unique constraint ignores the already-committed URLs.
            for _ in range(2):
                target = await _claim_specific_url(factory, source_id, root)
                result = await process_job(
                    target, session_factory=factory,
                    politeness_manager=manager, max_links=100,
                )
                assert result.outcome == "success"
                assert await page_count() == total

            async with factory() as session:
                target = await session.get(CrawlTarget, target.id)
                assert target.failure_count == 0
                attempts = await session.scalar(
                    select(func.count(CrawlAttempt.id)).where(
                        CrawlAttempt.crawl_target_id == target.id
                    )
                )
                assert attempts == 3

    asyncio.run(run())


ARTICLE = 'https://example.com/docs/article'
FEED = 'https://example.com/docs/feed'
OTHER_FEED = 'https://example.com/docs/other-feed'
PAGE_TEXT = 'Full article text about Python generators with many worked examples. ' * 20
SUMMARY = 'Short summary of the Python generators article.'


def _feed(body=SUMMARY):
    return (f'<rss><channel><item><link>{ARTICLE}</link><title>Python generators</title>'
            f'<description>{body}</description></item></channel></rss>').encode()


def _page(url=ARTICLE):
    return f'<html><head><title>Python generators</title></head><body><main><p>{PAGE_TEXT}</p></main></body></html>'.encode()


def serve(monkeypatch, responses):
    """responses maps a URL to (status, content type, body) or adds headers as a fourth item."""
    async def fetch(self, session, url):
        status, content_type, body, *rest = responses[url]
        return FetchResult(RobotsDecision.ALLOW, f'Fetched HTTP {status}', url, url, status_code=status,
            headers={'content-type': content_type, **(rest[0] if rest else {})}, body=body)
    monkeypatch.setattr(PolicyCoordinator, 'fetch', fetch)


async def add_targets(factory, source_id, *targets):
    async with factory() as session, session.begin():
        await enqueue_targets(session, [CrawlTargetCreate(source_id=source_id, kind=kind, fetch_url=url, normalized_url=url)
                                        for url, kind in targets])


async def crawl_url(factory, source_id, url):
    target = await _claim_specific_url(factory, source_id, url)
    return await process_job(target, session_factory=factory, politeness_manager=PolitenessManager(min_interval_seconds=0))


async def article(factory):
    async with factory() as session:
        return await session.scalar(select(Document).where(Document.canonical_url == ARTICLE))


async def drop_article(factory):
    """example.com is shared across tests, so no earlier row may hold this URL."""
    async with factory() as session, session.begin():
        await session.execute(delete(Document).where(Document.canonical_url == ARTICLE))


def test_feed_summary_never_replaces_a_fetched_page(monkeypatch):
    serve(monkeypatch, {ARTICLE: (200, 'text/html', _page()), FEED: (200, 'application/xml', _feed())})
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (ARTICLE, 'page'), (FEED, 'rss'))
            await crawl_url(factory, source_id, ARTICLE)
            page = await article(factory)
            assert 'worked examples' in page.body
            result = await crawl_url(factory, source_id, FEED)
            assert result.outcome == 'success' and result.documents_saved == 0
            kept = await article(factory)
            assert kept.body == page.body and kept.content_hash == page.content_hash
            assert kept.last_crawl_target_id == page.last_crawl_target_id
            assert kept.updated_at == page.updated_at  # the indexer has nothing to redo
            assert kept.last_seen_at > page.last_seen_at
            assert 'ingestion_format' not in kept.metadata_
            async with factory() as session:
                attempt = await session.get(CrawlAttempt, result.attempt_id)
            assert attempt.telemetry['documents'][0]['decision'] == 'kept_existing'
    asyncio.run(run())


def test_fetched_page_replaces_an_earlier_feed_summary(monkeypatch):
    serve(monkeypatch, {ARTICLE: (200, 'text/html', _page()), FEED: (200, 'application/xml', _feed())})
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (ARTICLE, 'page'), (FEED, 'rss'))
            await crawl_url(factory, source_id, FEED)
            summary = await article(factory)
            assert summary.metadata_['ingestion_format'] == 'rss' and summary.metadata_['feed_url'] == FEED
            await crawl_url(factory, source_id, ARTICLE)
            page = await article(factory)
            assert 'worked examples' in page.body and page.id == summary.id
            assert page.last_crawl_target_id != summary.last_crawl_target_id
            assert 'ingestion_format' not in page.metadata_
    asyncio.run(run())


def test_feed_updates_its_own_entry_but_another_feed_needs_more_text(monkeypatch):
    responses = {FEED: (200, 'application/xml', _feed('First version of a reasonably long Python summary here.')),
                 OTHER_FEED: (200, 'application/xml', _feed('Tiny Python note.'))}
    serve(monkeypatch, responses)
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (FEED, 'rss'), (OTHER_FEED, 'rss'))
            await crawl_url(factory, source_id, FEED)
            first = await article(factory)
            result = await crawl_url(factory, source_id, OTHER_FEED)
            assert result.documents_saved == 0 and (await article(factory)).body == first.body
            responses[FEED] = (200, 'application/xml', _feed('Edited Python summary.'))
            result = await crawl_url(factory, source_id, FEED)
            assert result.documents_saved == 1 and (await article(factory)).body == 'Edited Python summary.'
            responses[OTHER_FEED] = (200, 'application/xml', _feed('A longer Python note from the second feed, with more detail.'))
            result = await crawl_url(factory, source_id, OTHER_FEED)
            stored = await article(factory)
            assert result.documents_saved == 1 and stored.metadata_['feed_url'] == OTHER_FEED
    asyncio.run(run())


def test_stale_feed_entry_does_not_bring_back_a_removed_page(monkeypatch):
    responses = {ARTICLE: (200, 'text/html', _page()), FEED: (200, 'application/xml', _feed())}
    serve(monkeypatch, responses)
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (ARTICLE, 'page'), (FEED, 'rss'))
            await crawl_url(factory, source_id, ARTICLE)
            responses[ARTICLE] = (404, 'text/html', b'')
            await crawl_url(factory, source_id, ARTICLE)
            removed = await article(factory)
            assert removed.is_available is False and removed.unavailable_http_status == 404
            await crawl_url(factory, source_id, FEED)
            still = await article(factory)
            assert still.is_available is False and still.body == removed.body
            assert still.last_seen_at == removed.last_seen_at
    asyncio.run(run())


@pytest.mark.parametrize('status', [404, 410])
def test_missing_feed_leaves_its_articles_available(monkeypatch, status):
    responses = {FEED: (200, 'application/xml', _feed())}
    serve(monkeypatch, responses)
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (FEED, 'rss'))
            await crawl_url(factory, source_id, FEED)
            responses[FEED] = (status, 'application/xml', b'')
            await crawl_url(factory, source_id, FEED)
            stored = await article(factory)
            assert stored.is_available is True and stored.unavailable_at is None
    asyncio.run(run())


def test_missing_page_removes_a_document_a_feed_wrote(monkeypatch):
    serve(monkeypatch, {ARTICLE: (404, 'text/html', b''), FEED: (200, 'application/xml', _feed())})
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (ARTICLE, 'page'), (FEED, 'rss'))
            await crawl_url(factory, source_id, FEED)
            await crawl_url(factory, source_id, ARTICLE)
            stored = await article(factory)
            assert stored.is_available is False and stored.unavailable_http_status == 404
    asyncio.run(run())


def test_noindex_header_on_a_feed_does_not_touch_its_articles(monkeypatch):
    serve(monkeypatch, {ARTICLE: (200, 'text/html', _page()),
                        FEED: (200, 'application/xml', _feed(), {'X-Robots-Tag': 'noindex, follow'})})
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (ARTICLE, 'page'), (FEED, 'rss'))
            await crawl_url(factory, source_id, ARTICLE)
            await crawl_url(factory, source_id, FEED)
            assert (await article(factory)).is_available is True
    asyncio.run(run())


def test_noindex_page_is_removed_and_a_feed_cannot_bring_it_back(monkeypatch):
    responses = {ARTICLE: (200, 'text/html', _page()), FEED: (200, 'application/xml', _feed())}
    serve(monkeypatch, responses)
    async def run():
        async with database() as (factory, source_id):
            await drop_article(factory)
            await add_targets(factory, source_id, (ARTICLE, 'page'), (FEED, 'rss'))
            await crawl_url(factory, source_id, ARTICLE)
            responses[ARTICLE] = (200, 'text/html', _page(), {'X-Robots-Tag': 'noindex'})
            await crawl_url(factory, source_id, ARTICLE)
            removed = await article(factory)
            assert removed.is_available is False and removed.unavailable_http_status is None
            await crawl_url(factory, source_id, FEED)
            assert (await article(factory)).is_available is False
    asyncio.run(run())


def test_batched_progress_is_durable_and_terminal_summary_is_written_once():
    from crawler.worker.telemetry import checkpoint_batch
    from crawler.writer.attempts import finish_attempt

    async def run():
        async with database() as (factory, source_id):
            await seed(factory, source_id, 1)
            target = (await claim(factory, source_id))[0]
            async with factory() as session, session.begin():
                attempt_id = await start_attempt(session, target.id, lease_until=target.lease_until)
            await checkpoint_batch(factory, attempt_id, [
                ("PARSE", "success", {"documents": 1}),
                ("PROCESS", "accepted", {"accepted": 1}),
            ], {"parsed": True})
            async with factory() as session:
                attempt = await session.get(CrawlAttempt, attempt_id)
                assert attempt.finished_at is None and attempt.telemetry is None
                events = (await session.execute(select(CrawlEvent.stage).where(
                    CrawlEvent.attempt_id == attempt_id).order_by(CrawlEvent.id))).scalars().all()
                assert events == ["PARSE", "PROCESS"]
            failure = {"parsed": True, "error_category": "process"}
            await checkpoint_batch(factory, attempt_id, [("PROCESS", "failed", {"error": "failed"})], failure)
            async with factory() as session:
                assert (await session.get(CrawlAttempt, attempt_id)).telemetry == failure
            summary = {**failure, "stored": 0, "result": "failed"}
            async with factory() as session, session.begin():
                assert await finish_attempt(session, attempt_id, "failed", telemetry=summary)
            async with factory() as session:
                attempt = await session.get(CrawlAttempt, attempt_id)
                assert attempt.finished_at is not None and attempt.telemetry == summary
    asyncio.run(run())
