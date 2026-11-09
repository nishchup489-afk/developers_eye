"""Groq transport with no retries, no redirects, bounded reads and an outer deadline."""
import asyncio
import json
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from math import ceil, isfinite
from time import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from backend.ai_overview.prompt import OUTPUT_TOKENS, SYSTEM_PROMPT, parse_answer
from backend.ai_overview.store import Outcome
from backend.core.config import settings
from backend.schema.ai_overview import OverviewContext

PROVIDER_URL = "https://api.groq.com/openai/v1/chat/completions"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def retry_seconds(header: str | None) -> int:
    try:
        seconds = float(header)
    except (TypeError, ValueError):
        try:
            seconds = parsedate_to_datetime(header).timestamp() - time()
        except (TypeError, ValueError, OverflowError):
            return 60
    return max(1, ceil(seconds)) if isfinite(seconds) and seconds > 0 else 60


def _request(content: str) -> tuple[int, dict, bytes]:
    body = json.dumps({"model": settings.groq_model, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
        "temperature": 0.2, "max_completion_tokens": OUTPUT_TOKENS,
        "response_format": {"type": "json_object"},
        **({"reasoning_effort": "none"} if settings.groq_model == "qwen/qwen3.8-27b" else {})}).encode()
    request = Request(PROVIDER_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + settings.groq_api_key.get_secret_value(),
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "developers-eye/0.1"})
    opener = build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            data = response.read(65537)
            if len(data) > 65536:
                raise ValueError("Oversized provider response")
            return response.status, dict(response.headers), data
    except HTTPError as error:
        # Never read or expose provider diagnostic bodies or credentials.
        with error:
            return error.code, dict(error.headers), b""


async def generate(context: OverviewContext, content: str) -> Outcome:
    try:
        async with asyncio.timeout(12):
            status, headers, body = await asyncio.to_thread(_request, content)
        if status == 429:
            header = next((value for key, value in headers.items() if key.lower() == "retry-after"), None)
            return Outcome(status=429, retry_after=retry_seconds(header),
                           error="AI overview has reached its limit. Your search results are ready below.")
        if status != 200:
            raise ValueError("Provider unavailable")
        choice = json.loads(body)["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Incomplete overview")
        overview = parse_answer(choice["message"]["content"], context)
        return Outcome(overview=overview.model_dump() if overview else None)
    except TimeoutError:
        return Outcome(status=504, error="AI overview timed out. Explore the sources below.")
    except URLError as error:
        return Outcome(status=504 if isinstance(error.reason, TimeoutError) else 502,
                       error="AI overview is unavailable right now. Explore the sources below.")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, OSError, HTTPException):
        return Outcome(status=502, error="AI overview is unavailable right now. Explore the sources below.")
