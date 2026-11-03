import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql

from crawler.schedular import repository
from crawler.worker import recovery, runner
from crawler.writer.attempts import close_abandoned_attempts

NOW = datetime.now(timezone.utc)


class Session:
    def __init__(self, target=None, groups=()):
        self.target, self.groups, self.queries, self.events = target, iter(groups), [], []
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    @asynccontextmanager
    async def begin(self): yield self
    async def scalar(self, query):
        return NOW if 'clock_timestamp' in str(query) else self.target
    async def scalars(self, query):
        self.queries.append(query)
        return SimpleNamespace(all=lambda: next(self.groups))
    def add(self, item): self.events.append(item)


def test_abandoned_attempt_is_terminal_and_preserves_original_failure_category():
    lease = NOW - timedelta(seconds=1)
    attempt = SimpleNamespace(id=11, started_at=NOW - timedelta(minutes=5), telemetry={'error_category': 'persistence'}, finished_at=None)
    session = Session(groups=([attempt],))
    assert asyncio.run(close_abandoned_attempts(session, 1, 'worker', 'Storage failed', lease_until=lease)) == 1
    assert attempt.finished_at == NOW
    assert attempt.outcome == 'failed'
    assert attempt.telemetry['error_category'] == 'persistence'
    assert session.events[0].outcome == 'failed'
    sql = session.queries[0].compile(dialect=postgresql.dialect())
    assert 'crawl_attempt.lease_until =' in str(sql)
    assert lease in sql.params.values()


def test_recovery_never_requeues_a_newer_workers_claim(monkeypatch):
    old_lease = NOW + timedelta(minutes=1)
    session = Session(target=SimpleNamespace(state='leased', lease_until=NOW + timedelta(minutes=5)))
    close = AsyncMock()
    fail = AsyncMock()
    monkeypatch.setattr(recovery, 'close_abandoned_attempts', close)
    monkeypatch.setattr(recovery, 'fail_target', fail)
    asyncio.run(recovery.recover_failed_claim(lambda: session, 1, old_lease, 'timeout', 'Deadline exceeded'))
    fail.assert_not_awaited()
    assert close.call_args.kwargs == {'lease_until': old_lease, 'include_legacy': False}


def test_owned_failure_uses_scheduler_backoff(monkeypatch):
    lease = NOW + timedelta(minutes=1)
    session = Session(target=SimpleNamespace(state='leased', lease_until=lease))
    monkeypatch.setattr(recovery, 'close_abandoned_attempts', AsyncMock())
    fail = AsyncMock(return_value=True)
    monkeypatch.setattr(recovery, 'fail_target', fail)
    asyncio.run(recovery.recover_failed_claim(lambda: session, 1, lease, 'timeout', 'Deadline exceeded'))
    fail.assert_awaited_once_with(session, 1, lease)


def test_expired_leases_increment_failures_delay_retries_and_reconcile_orphans(monkeypatch):
    target = SimpleNamespace(id=1, failure_count=1, state='leased', lease_until=NOW - timedelta(seconds=1))
    orphan = SimpleNamespace(id=2, state='queued')
    session = Session(groups=([target], [orphan]))
    close = AsyncMock()
    monkeypatch.setattr(repository, 'close_abandoned_attempts', close)
    assert asyncio.run(repository.recover_expired_leases(session)) == 1
    assert target.failure_count == 2
    assert target.next_fetch_at == NOW + timedelta(seconds=120)
    assert target.state == 'queued' and target.lease_until is None
    assert close.await_count == 2
    assert 'SKIP LOCKED' in str(session.queries[0].compile(dialect=postgresql.dialect()))
    assert 'crawl_target.state !=' in str(session.queries[1])


def test_timeout_records_exact_claim_and_is_counted_as_failed(monkeypatch):
    target = SimpleNamespace(id=1, source_id=1, fetch_url='https://example.com', lease_until=NOW + timedelta(minutes=5))
    record = AsyncMock()
    monkeypatch.setattr(runner, 'record_runner_failure', record)
    async def slow(target): await asyncio.sleep(1)
    report = runner.BatchReport()
    asyncio.run(runner.execute_target(target, job_handler=slow, semaphore=asyncio.Semaphore(1),
        config=runner.RunnerConfig(job_timeout_seconds=.01), report=report))
    assert report.failed == report.timed_out == 1
    assert record.call_args.args[0] is target
