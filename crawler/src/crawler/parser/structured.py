"""Shared, network-free helpers for feed and JSON document records."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.frontier.urls import normalize_url
from crawler.policy_and_politeness.host_policy import has_suspicious_characters


def resolve_record_url(value: object, base: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if has_suspicious_characters(value):
        return None
    try:
        return normalize_url(urljoin(base, value))
    except (TypeError, ValueError):
        return None


def readable_markup(value: str) -> str:
    soup = BeautifulSoup(value, "lxml")
    for element in soup.select("script, style, noscript, template, iframe, object"):
        element.decompose()
    return soup.get_text("\n", strip=True)


def parse_record_date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip())
    except ValueError:
        try:
            result = parsedate_to_datetime(value.strip())
        except (ValueError, TypeError, OverflowError):
            return None
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
