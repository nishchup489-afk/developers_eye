"""Public overview endpoint: backend owns validation, key, prompt and quotas."""
import hashlib

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.ai_overview import service
from backend.ai_overview.context import enabled, verify_context
from backend.core.config import settings
from backend.schema.ai_overview import OverviewRequest, OverviewResponse

router = APIRouter(tags=["search"])


def _json(body, status=200, retry_after=None):
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store",
        **({"Retry-After": str(retry_after)} if retry_after else {})})


@router.post("/search/overview", response_model=OverviewResponse)
async def search_overview(request: Request):
    if request.headers.get("sec-fetch-site") == "cross-site":
        return _json({"error": "Use AI overview from this site."}, 403)
    if not enabled():
        return _json({"overview": None})
    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        return _json({"error": "Expected JSON."}, 415)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 25000:
            return _json({"error": "Search context too large."}, 413)
    try:
        body = OverviewRequest.model_validate_json(raw)
    except (ValidationError, ValueError):
        return _json({"error": "Invalid search context."}, 400)
    context = verify_context(body.token)
    if context is None:
        return _json({"error": "Refresh your search to generate an overview."}, 400)
    # Trust only a deployment-configured header overwritten by the ingress.
    # In edge-authenticated deployments the middleware already validated and set
    # request.client. A caller must not override that identity via another header.
    header = "" if settings.edge_shared_secret else settings.ai_overview_client_ip_header
    identity = (request.headers.get(header) if header else None) or (request.client.host if request.client else "anonymous")
    client = hashlib.sha256(identity[:200].encode()).hexdigest()
    outcome = await service.overview(context, client)
    return _json(outcome.body(), outcome.status, outcome.retry_after)
