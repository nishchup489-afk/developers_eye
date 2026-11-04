"""Service-authenticated HTTP adapter for capacity, host and problem reporting."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from backend.api.crawler_report import monitor_query, require_report_key

router = APIRouter(prefix="/admin/system", tags=["system reporting"])


@router.get("/report", dependencies=[Depends(require_report_key)])
async def system_report(response: Response, days: Annotated[int, Query(ge=1, le=90)] = 7):
    from backend.admin_services.system_reporting import build_system_report
    return await monitor_query(response, build_system_report, days=days)


@router.get("/hosts", dependencies=[Depends(require_report_key)])
async def host_report(response: Response, minutes: Annotated[int, Query(ge=5, le=1440)] = 60):
    from backend.admin_services.system_reporting import build_host_report
    return await monitor_query(response, build_host_report, minutes=minutes)


@router.get("/problems", dependencies=[Depends(require_report_key)])
async def problems(response: Response):
    from backend.admin_services.system_reporting import build_problems
    return await monitor_query(response, build_problems)
