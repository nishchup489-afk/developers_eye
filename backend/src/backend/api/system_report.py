"""Service-authenticated HTTP adapter for capacity, host and problem reporting."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.api.crawler_report import monitor_query, require_report_key
from backend.db.session import SessionFactory

router = APIRouter(prefix="/admin/system", tags=["system reporting"])
logger = logging.getLogger(__name__)
# Below the frontend's 15 s proxy timeout, so a hung database still gets an answer.
SEARCH_REPORT_SECONDS = 5.0


@router.get("/report", dependencies=[Depends(require_report_key)])
async def system_report(response: Response, days: Annotated[int, Query(ge=1, le=90)] = 7):
    from backend.admin_services.system_reporting import build_system_report
    return await monitor_query(response, build_system_report, days=days)


@router.get("/hosts", dependencies=[Depends(require_report_key)])
async def host_report(response: Response, minutes: Annotated[int, Query(ge=5, le=1440)] = 60):
    from backend.admin_services.system_reporting import build_host_report
    return await monitor_query(response, build_host_report, minutes=minutes)


@router.get("/corpus", dependencies=[Depends(require_report_key)])
async def corpus_report(response: Response):
    from backend.admin_services.corpus_reporting import build_corpus_report
    return await monitor_query(response, build_corpus_report)


@router.get("/search", dependencies=[Depends(require_report_key)])
async def search_report(response: Response, hours: Annotated[int, Query(ge=1, le=168)] = 24):
    from backend.admin_services.search_reporting import build_offline_report, build_search_report
    response.headers["Cache-Control"] = "private, no-store"
    try:
        async with asyncio.timeout(SEARCH_REPORT_SECONDS), SessionFactory() as session:
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            return await build_search_report(session, hours=hours)
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        # This report exists for outages, so it answers instead of returning 503.
        logger.warning("Search availability report could not reach the database (%s)", type(exc).__name__)
        return build_offline_report(hours=hours)


@router.get("/problems", dependencies=[Depends(require_report_key)])
async def problems(response: Response):
    from backend.admin_services.system_reporting import build_problems
    return await monitor_query(response, build_problems)
