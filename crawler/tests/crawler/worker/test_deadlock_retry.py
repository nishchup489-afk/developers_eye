import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import DBAPIError

from crawler.worker.jobs import jobs


class DatabaseFailure(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


def error(sqlstate='40P01'):
    return DBAPIError('statement', {}, DatabaseFailure(sqlstate), False)


def test_deadlock_retries_fresh_operation_without_refetch(monkeypatch):
    operation = AsyncMock(side_effect=[error(), error(), 'saved'])
    sleep = AsyncMock()
    monkeypatch.setattr(jobs.asyncio, 'sleep', sleep)
    monkeypatch.setattr(jobs.random, 'uniform', lambda *args: 0)
    assert asyncio.run(jobs.retry_deadlocked_finalization(operation)) == 'saved'
    assert operation.await_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [.2, .4]


def test_deadlock_exhaustion_propagates_last_error(monkeypatch):
    failure = error()
    operation = AsyncMock(side_effect=failure)
    monkeypatch.setattr(jobs.asyncio, 'sleep', AsyncMock())
    with pytest.raises(DBAPIError) as caught:
        asyncio.run(jobs.retry_deadlocked_finalization(operation))
    assert caught.value is failure
    assert operation.await_count == 4


def test_other_database_errors_and_cancellation_are_not_retried():
    for failure in [error('23505'), asyncio.CancelledError()]:
        operation = AsyncMock(side_effect=failure)
        with pytest.raises(type(failure)):
            asyncio.run(jobs.retry_deadlocked_finalization(operation))
        assert operation.await_count == 1
