"""Service-authenticated HTTP adapter for the crawler's existing report builder."""

import logging
import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from backend.core.config import settings
from backend.db.session import SessionFactory

router = APIRouter(prefix="/admin/crawler", tags=["crawler reporting"])
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def require_report_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    key = settings.crawler_report_api_key
    if not key or len(key.get_secret_value()) < 32:
        raise HTTPException(503, "Crawler reporting API key is not configured")
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), key.get_secret_value().encode()
    ):
        raise HTTPException(401, "Invalid reporting credentials", headers={"WWW-Authenticate": "Bearer"})


@router.get("/report", dependencies=[Depends(require_report_key)])
async def crawler_report(
    response: Response,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    top_sources: Annotated[int, Query(ge=1, le=100)] = 20,
    recent_errors: Annotated[int, Query(ge=0, le=100)] = 20,
) -> dict:
    # Crawler is a sibling package. Run with both src directories on PYTHONPATH.
    try:
        from crawler.worker.reporting import build_report
    except ModuleNotFoundError as exc:
        logger.error("Crawler reporting package is unavailable: %s", exc.name)
        raise HTTPException(503, "Crawler package is not available in the backend environment") from exc
    response.headers["Cache-Control"] = "private, no-store"
    try:
        async with SessionFactory() as session:
            return await build_report(session, days=days, top_sources=top_sources, recent_errors=recent_errors)
    except SQLAlchemyError as exc:
        logger.error("Crawler report database query failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Crawler reporting database is unavailable") from exc


async def monitor_query(response, handler, **kwargs):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        async with SessionFactory() as session:
            # All counts in one response observe the same committed snapshot.
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            result = await handler(session, **kwargs)
            if result is None:
                raise HTTPException(404, "Crawler record not found")
            return result
    except SQLAlchemyError as exc:
        logger.error("Crawler monitoring query failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Crawler monitoring is unavailable. Apply database migrations and check the database connection.") from exc


@router.get("/monitor", dependencies=[Depends(require_report_key)])
async def crawler_monitor(
    response: Response,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
    source_id: Annotated[int | None, Query(gt=0)] = None,
    status: Literal["running", "success", "failed", "blocked", "accepted", "skipped", "persisted", "not_stored", "duplicate", "new", "updated", "unchanged", "not_modified", "stale", "complete"] | None = None,
    category: Literal["fetch", "parse", "process", "processing", "dedup", "store", "discover", "finalize", "worker"] | None = None,
    q: Annotated[str, Query(max_length=200)] = "",
    document_page: Annotated[int, Query(ge=0, le=10000)] = 0,
    frontier_page: Annotated[int, Query(ge=0, le=10000)] = 0,
    frontier_state: Literal["due", "scheduled", "expired", "retry", "queued", "leased", "blocked", "disabled"] | None = None,
    before_event_id: Annotated[int | None, Query(gt=0)] = None,
):
    from crawler.worker.monitoring import build_monitor
    return await monitor_query(response, build_monitor, days=days, source_id=source_id, status=status,
        category=category, q=q, document_page=document_page, frontier_page=frontier_page,
        frontier_state=frontier_state, before_event_id=before_event_id)


@router.get("/documents/{document_id}", dependencies=[Depends(require_report_key)])
async def crawler_document(response: Response, document_id: Annotated[int, Path(gt=0)]):
    from crawler.worker.monitoring import inspect_document
    return await monitor_query(response, inspect_document, document_id=document_id)


@router.get("/attempts/{attempt_id}", dependencies=[Depends(require_report_key)])
async def crawler_attempt(response: Response, attempt_id: Annotated[int, Path(gt=0)]):
    from crawler.worker.monitoring import inspect_attempt
    return await monitor_query(response, inspect_attempt, attempt_id=attempt_id)
