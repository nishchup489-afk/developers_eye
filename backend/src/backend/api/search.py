"""GET /search, serving the same response shape as the Next.js bridge.

Request limits, in the order a request meets them:
1. Per-client rate limit (HTTP 429 with Retry-After).
2. Query validation (HTTP 422).
3. Concurrency cap per process (HTTP 503 with Retry-After).
4. Total deadline over the whole search, and a PostgreSQL statement_timeout
   on every statement (HTTP 504 either way).
5. A client that disconnects cancels its search; nobody receives the 499.
"""

import asyncio
import logging
import math
import os
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.request_limits import (
    CLIENT_CLOSED_REQUEST,
    ClientDisconnected,
    RateLimiter,
    client_key,
    run_unless_disconnected,
)
from backend.db.session import DATABASE_UNAVAILABLE_ERRORS, SessionFactory
from backend.ai_overview.context import sign_context
from backend.schema.search import SearchFilter, SearchResponseOut
from backend.schema.search_term import QueryCorrection
from backend.search.query_analyzer.analyzer import QueryValidationError, analyze_query
from backend.search.query_selector.planner import SearchMode
from backend.search.service import search_documents
from backend.search.retrieval.fuzzy.correction import suggest_query_correction
from backend.search.telemetry import telemetry
from backend.search.trace import stage_summary, started_trace

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])

MAX_CONCURRENT_SEARCHES = int(os.environ.get("SEARCH_MAX_CONCURRENT", "16"))
QUERY_DEADLINE_MS = int(os.environ.get("SEARCH_QUERY_DEADLINE_MS", "3000"))
# Whole request: waiting for a pooled connection, every statement and ranking.
# Keep it above SEARCH_QUERY_DEADLINE_MS and below the Next.js proxy timeout (6 s).
TOTAL_DEADLINE_SECONDS = int(os.environ.get("SEARCH_TOTAL_DEADLINE_MS", "4000")) / 1000
RATE_LIMIT_PER_MINUTE = int(os.environ.get("SEARCH_RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_BURST = int(os.environ.get("SEARCH_RATE_LIMIT_BURST", "20"))

# Shared by searches and suggestions, which draw on the same connection pool.
_in_flight = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
# Searches and suggestions have separate budgets: one results page makes one of each.
search_rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE, RATE_LIMIT_BURST)
suggest_rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE, RATE_LIMIT_BURST)
# PostgreSQL query_canceled, which statement_timeout raises.
QUERY_CANCELED = "57014"


async def apply_query_deadline(session: AsyncSession) -> None:
    """Cancel any statement of this search that runs past the deadline."""
    await session.execute(select(func.set_config("statement_timeout", str(QUERY_DEADLINE_MS), True)))


def _is_database_timeout(exc: SQLAlchemyError) -> bool:
    """A statement cancelled by statement_timeout, or no pooled connection in time."""
    if isinstance(exc, PoolTimeoutError):
        return True
    return getattr(getattr(exc, "orig", None), "sqlstate", None) == QUERY_CANCELED


async def _try_take_slot() -> bool:
    """Take a concurrency slot without queueing, or return False when none is free.

    acquire() does not yield to the event loop when a slot is free, so no other request
    can run between the check and the acquire and the cap cannot be overshot.
    """
    if _in_flight.locked():
        return False
    await _in_flight.acquire()
    return True


def _enforce_rate_limit(limiter: RateLimiter, request: Request, what: str) -> None:
    wait = limiter.acquire(client_key(request))
    if wait > 0:
        raise HTTPException(
            429,
            f"Too many {what}; slow down",
            headers={"Retry-After": str(max(1, math.ceil(wait))), "Cache-Control": "no-store"},
        )


@router.get("/search", response_model=SearchResponseOut)
async def search(
    request: Request,
    response: Response,
    q: Annotated[str, Query(max_length=1024)],
    source: SearchFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    page: Annotated[int, Query(ge=1)] = 1,
    mode: SearchMode = SearchMode.ALL,
    language: Annotated[str | None, Query(pattern=r"^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8}){0,2}$", max_length=35)] = None,
) -> SearchResponseOut | Response:
    _enforce_rate_limit(search_rate_limiter, request, "searches")
    try:
        normalized = analyze_query(q)
    except QueryValidationError as exc:
        telemetry.record("invalid")
        raise HTTPException(422, str(exc)) from exc

    response.headers["Cache-Control"] = "no-store"
    if not await _try_take_slot():
        telemetry.record("busy")
        raise HTTPException(503, "Search is busy; try again shortly", headers={"Retry-After": "1"})

    async def run() -> list:
        async with SessionFactory() as session:
            await apply_query_deadline(session)
            # Preserve the previous call signature for default requests.
            extra = {}
            if page != 1:
                extra["page"] = page
            if mode is not SearchMode.ALL:
                extra["mode"] = mode
            if language is not None:
                extra["language"] = language
            return await search_documents(
                session, normalized, category=source, limit=limit, **extra
            )

    started = perf_counter()
    trace = started_trace()

    def record_slow(outcome: str, result_count: int | None = None) -> None:
        stages, stopped_in = stage_summary(trace)
        telemetry.record_slow(
            query=normalized, mode=mode.value, category=source, page=page,
            outcome=outcome, elapsed_ms=(perf_counter() - started) * 1000, result_count=result_count,
            stages=stages, stopped_in=None if outcome == "successful" else stopped_in,
        )

    try:
        async with asyncio.timeout(TOTAL_DEADLINE_SECONDS):
            results = await run_unless_disconnected(request, run())
    except ClientDisconnected:
        # The search was cancelled; this response is never delivered.
        return Response(status_code=CLIENT_CLOSED_REQUEST)
    except TimeoutError as exc:
        telemetry.record("timed_out")
        record_slow("timed_out")
        raise HTTPException(504, "Search timed out") from exc
    except (ValueError, QueryValidationError) as exc:
        telemetry.record("invalid")
        raise HTTPException(422, str(exc)) from exc
    except (SQLAlchemyError, *DATABASE_UNAVAILABLE_ERRORS) as exc:
        if _is_database_timeout(exc):
            telemetry.record("timed_out")
            record_slow("timed_out")
            raise HTTPException(504, "Search timed out") from exc
        telemetry.record("database_errors")
        logger.exception("Search database failure")
        raise HTTPException(503, "Search database is unavailable") from exc
    except RuntimeError as exc:
        telemetry.record("engine_errors")
        logger.error("Search engine unavailable: %s", type(exc).__name__)
        raise HTTPException(503, "Search engine is not initialized") from exc
    except Exception:
        telemetry.record("server_errors")
        raise
    finally:
        # run_unless_disconnected has already waited for the search to unwind.
        _in_flight.release()

    telemetry.record("successful", (perf_counter() - started) * 1000)
    record_slow("successful", len(results))
    # ADR-0049: backend issues evidence; overview generation is a separate request.
    return SearchResponseOut(query=normalized, results=results, overview_token=sign_context(normalized, results))


@router.get("/search/suggest", response_model=QueryCorrection)
async def suggest_search_query(
    request: Request,
    q: Annotated[str, Query(max_length=1024)],
) -> QueryCorrection | Response:
    """Explicit spelling suggestion from the indexer-maintained vocabulary."""
    _enforce_rate_limit(suggest_rate_limiter, request, "suggestions")
    try:
        normalized = analyze_query(q)
    except QueryValidationError as exc:
        raise HTTPException(422, str(exc)) from exc

    if not await _try_take_slot():
        raise HTTPException(503, "Search suggestions are busy; try again shortly", headers={"Retry-After": "1"})

    async def run() -> QueryCorrection:
        async with SessionFactory() as session:
            await apply_query_deadline(session)
            return await suggest_query_correction(normalized, session)

    try:
        async with asyncio.timeout(TOTAL_DEADLINE_SECONDS):
            return await run_unless_disconnected(request, run())
    except ClientDisconnected:
        return Response(status_code=CLIENT_CLOSED_REQUEST)
    except TimeoutError as exc:
        raise HTTPException(504, "Search suggestions timed out") from exc
    except (ValueError, QueryValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except (SQLAlchemyError, *DATABASE_UNAVAILABLE_ERRORS) as exc:
        if _is_database_timeout(exc):
            raise HTTPException(504, "Search suggestions timed out") from exc
        logger.exception("Vocabulary suggestion query failed")
        raise HTTPException(503, "Search suggestions are unavailable") from exc
    finally:
        _in_flight.release()
