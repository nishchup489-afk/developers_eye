"""Issue and verify bounded evidence; the frontend never owns the signing key."""
import base64
import hashlib
import hmac
import time

from pydantic import ValidationError

from backend.core.config import settings
from backend.schema.ai_overview import OverviewContext, OverviewSource
from backend.schema.search import SearchResultOut


def enabled() -> bool:
    return bool(settings.ai_overview and settings.groq_api_key and settings.groq_api_key.get_secret_value().strip())


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _signature(payload: str) -> str:
    key = settings.groq_api_key.get_secret_value().encode()
    return _encode(hmac.new(key, ("developers-eye-overview-v2:" + payload).encode(), hashlib.sha256).digest())


def sign_context(query: str, results: list[SearchResultOut]) -> str | None:
    if not enabled():
        return None
    sources, seen = [], set()
    for result in results:
        if len(sources) == 4:
            break
        if not result.snippet.strip() or result.url in seen:
            continue
        try:
            source = OverviewSource(id=len(sources) + 1, title=result.title[:120], url=result.url,
                                    snippet=result.snippet[:350], kind=result.source)
        except ValidationError:
            continue
        seen.add(result.url)
        sources.append(source)
    if not sources:
        return None
    context = OverviewContext(query=query, sources=sources, expires=time.time() + 600)
    payload = _encode(context.model_dump_json().encode())
    return payload + "." + _signature(payload)


def verify_context(token: str) -> OverviewContext | None:
    if not enabled() or len(token) > 24000:
        return None
    try:
        payload, signature = token.split(".")
        if not hmac.compare_digest(signature, _signature(payload)):
            return None
        data = base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True)
        context = OverviewContext.model_validate_json(data)
        return context if context.expires > time.time() else None
    except (ValueError, TypeError, UnicodeError, ValidationError):
        return None
