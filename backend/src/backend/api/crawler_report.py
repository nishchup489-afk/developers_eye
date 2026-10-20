"""Service-authenticated HTTP adapter for the crawler's existing report builder."""

import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

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
