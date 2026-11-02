"""Service-authenticated HTTP adapter for read-only indexer reporting."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from backend.api.crawler_report import monitor_query, require_report_key
from backend.core.config import settings

router = APIRouter(prefix="/admin/indexer", tags=["indexer reporting"])


@router.get("/report", dependencies=[Depends(require_report_key)])
async def indexer_report(
    response: Response,
    source_id: Annotated[int | None, Query(gt=0)] = None,
):
    from backend.admin_services.indexer_reporting import build_indexer_report
    return await monitor_query(response, build_indexer_report,
        index_version=settings.indexer_index_version, source_id=source_id)


@router.get("/vocabulary", dependencies=[Depends(require_report_key)])
async def vocabulary_report(
    response: Response,
    q: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
):
    from backend.admin_services.vocabulary_reporting import build_vocabulary_report
    return await monitor_query(response, build_vocabulary_report, query=q.strip() if q else None)
