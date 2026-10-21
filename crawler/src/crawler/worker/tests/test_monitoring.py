"""Network-free regression tests for pipeline instrumentation and authenticated reads."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql

from backend.api import crawler_report as api
from crawler.parser.schemas import ParsedDocument
from crawler.processing import process_document
from crawler.processing.schemas import ProcessingResult
from crawler.policy_and_politeness.policy_coordinator import FetchResult
from crawler.policy_and_politeness.robots_policy import RobotsDecision
from crawler.worker.jobs import jobs, utility
from crawler.worker.telemetry import checkpoint


class Session:
    def __init__(self, results=()):
        self.results = iter(results)
        self.events = []
        self.statements = []

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False

    @asynccontextmanager
    async def begin(self): yield self

    async def scalar(self, query):
        self.statements.append(query)
        return next(self.results)

    async def execute(self, query):
        # PostgreSQL compilation also catches ambiguous FROMs and invalid ORM mappings.
        str(query.compile(dialect=postgresql.dialect()))
        self.statements.append(query)

    async def get(self, cls, id): return SimpleNamespace(is_enabled=True, allowed_hosts=["example.com"], crawl_interval_seconds=60, config={})
    def add(self, value): self.events.append(value)


@pytest.mark.parametrize("scenario", ["stored", "noindex", "http404", "mime", "parse_error", "blocked", "not_modified", "store_error"])
def test_real_parser_pipeline_checkpoints(monkeypatch, scenario):
    async def run():
        now = datetime.now(timezone.utc)
        target = SimpleNamespace(id=1, source_id=1, fetch_url="https://example.com/docs", state="leased", lease_until=now + timedelta(minutes=5), kind="page", depth=0)
        session = Session([target, now])
        factory = lambda: session
        body = b'<html><head><title>Testing Python</title></head><body><main><h1>Testing Python</h1><p>Use async await to write concurrent programs and schedule tasks with Python.</p></main></body></html>'
        headers = {"content-type": "application/pdf" if scenario == "mime" else "text/html"}
        if scenario == "noindex": headers["x-robots-tag"] = "noindex"
        fetched = FetchResult(decision=RobotsDecision.DENY if scenario == "blocked" else RobotsDecision.ALLOW,
            reason="Test policy", requested_url=target.fetch_url, final_url=target.fetch_url,
            status_code=404 if scenario == "http404" else 304 if scenario == "not_modified" else 200,
            headers=headers, body=body)
        monkeypatch.setattr(jobs.PolicyCoordinator, "fetch", AsyncMock(return_value=fetched))
        monkeypatch.setattr(jobs, "start_attempt", AsyncMock(return_value=11))
        checkpoints = []
        async def capture(factory, id, stage, outcome, details=None, measurements=None):
            checkpoints.append((stage, outcome, dict(measurements or {})))
        monkeypatch.setattr(jobs, "checkpoint", capture)
        if scenario == "parse_error": monkeypatch.setattr(jobs, "parse", lambda **kwargs: (_ for _ in ()).throw(ValueError("broken markup")))
        final = AsyncMock(side_effect=RuntimeError("storage rejected") if scenario == "store_error" else None)
        monkeypatch.setattr(jobs, "_finalize", final)
        monkeypatch.setattr(jobs, "recover_failed_claim", AsyncMock())
        if scenario == "store_error":
            with pytest.raises(RuntimeError): await jobs.process_job(target, politeness_manager=object(), session_factory=factory)
            assert checkpoints[-1][0:2] == ("STORE", "failed")
            assert checkpoints[-1][2]["stored"] == 0
            jobs.recover_failed_claim.assert_awaited_once()
        else:
            await jobs.process_job(target, politeness_manager=object(), session_factory=factory)
        args = final.call_args.kwargs
        assert checkpoints[0][0:2] == ("FETCH", "running")
        assert args["measurements"]["fetch_success"] == (scenario not in {"http404", "blocked"})
        if scenario in {"stored", "store_error"}:
            assert args["measurements"]["parsed"] is True
            assert args["measurements"]["accepted"] == 1
            assert any(stage == "PARSE" for stage, _, _ in checkpoints)
        if scenario == "noindex":
            assert args["measurements"]["accepted"] == 0
            assert args["measurements"]["skipped"][0]["reason"] == "noindex"
        if scenario == "parse_error": assert args["measurements"]["error_category"] == "parse"
        if scenario == "mime": assert "unsupported MIME" in args["message"]
    asyncio.run(run())


@pytest.mark.parametrize("decision", ["new", "unchanged", "updated", "duplicate", "stale"])
def test_atomic_storage_events_and_dedup(monkeypatch, decision):
    async def run():
        now = datetime.now(timezone.utc)
        lease = now + timedelta(minutes=5)
        target = SimpleNamespace(source_id=1, state="leased", lease_until=now - timedelta(seconds=1) if decision == "stale" else lease)
        document = process_document(ParsedDocument(url="https://example.com/docs", title="Python", body="A useful Python documentation page with sample code."))
        previous = SimpleNamespace(content_hash=document.content_hash if decision == "unchanged" else "older") if decision in {"unchanged", "updated"} else None
        results = [target, now] if decision == "stale" else [target, now, True, previous, 99 if decision == "duplicate" else None]
        session = Session(results)
        monkeypatch.setattr(utility, "complete_target", AsyncMock(return_value=True))
        monkeypatch.setattr(utility, "upsert_document", AsyncMock(return_value=42))
        monkeypatch.setattr(utility, "finish_attempt", AsyncMock(return_value=True))
        result = await utility._finalize(session_factory=lambda: session, target_id=1, source_id=1,
            expected_lease_until=lease, attempt_id=11, action="complete", outcome="success", message="Processed",
            http_status=200, body_bytes=500, retry_after_seconds=None, interval_seconds=60,
            parsed=SimpleNamespace(discovered_links=[], documents=[]), processed=ProcessingResult(source_url=document.url, documents=(document,)),
            targets=[], elapsed=.25, measurements={"version": 1, "stored": 0})
        if decision == "stale":
            utility.upsert_document.assert_not_awaited()
            assert result.outcome == "stale"
            assert session.events[-1].outcome == "stale"
        else:
            assert result.documents_saved == 1
            dedup = next(e for e in session.events if e.stage == "DEDUP")
            assert dedup.outcome == decision
            assert next(e for e in session.events if e.stage == "STORE").details["documents"][0]["id"] == 42
            if decision == "duplicate": assert dedup.details["matching_document_id"] == 99
    asyncio.run(run())


def test_telemetry_failure_does_not_fail_crawl():
    def broken(): raise RuntimeError("database down")
    asyncio.run(checkpoint(broken, 1, "FETCH", "running"))


def test_monitoring_routes_enforce_auth_and_validate_filters(monkeypatch):
    app = FastAPI(); app.include_router(api.router)
    monkeypatch.setattr(api.settings, "crawler_report_api_key", SecretStr("a" * 32))
    session = Session()
    monkeypatch.setattr(api, "SessionFactory", lambda: session)
    import backend.services.crawler_monitoring as monitoring
    handler = AsyncMock(return_value={"version": 1})
    monkeypatch.setattr(monitoring, "build_monitor", handler)
    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in ["/monitor", "/documents/1", "/attempts/1"]:
                assert (await client.get("/admin/crawler" + path)).status_code == 401
            handler.assert_not_awaited()
            headers = {"Authorization": "Bearer " + "a" * 32}
            assert (await client.get("/admin/crawler/monitor?days=0", headers=headers)).status_code == 422
            assert (await client.get("/admin/crawler/monitor?status=invented", headers=headers)).status_code == 422
            response = await client.get("/admin/crawler/monitor?days=1&source_id=7&status=skipped", headers=headers)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            assert handler.call_args.kwargs["source_id"] == 7
            assert "READ ONLY" in str(session.statements[0])
    asyncio.run(run())
