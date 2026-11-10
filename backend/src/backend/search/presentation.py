"""Conservative, explainable metadata for language and documentation variants."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

LANGUAGE_TAG = re.compile(r"^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8}){0,2}$")
DOC_HOSTS = {"fastapi.tiangolo.com", "docs.python.org", "docs.djangoproject.com", "developer.mozilla.org"}
VERSION = re.compile(r"^\d+(?:\.\d+){0,2}$")


def result_identity(url: str, metadata: object) -> tuple[str | None, str | None, str]:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    parts = [part for part in parsed.path.split("/") if part]
    data = metadata if isinstance(metadata, dict) else {}
    language = data.get("language")
    language = language.lower() if isinstance(language, str) and LANGUAGE_TAG.fullmatch(language) else None
    version = None
    if host in DOC_HOSTS:
        if parts and LANGUAGE_TAG.fullmatch(parts[0]) and parts[0].lower() not in {"api", "web", "faq"}:
            language = language or parts[0].lower()
            parts.pop(0)
        elif host == "fastapi.tiangolo.com":
            language = language or "en"  # English uses unprefixed canonical paths.
        if host in {"docs.python.org", "docs.djangoproject.com"} and parts and VERSION.fullmatch(parts[0]):
            version = parts.pop(0)
    group = host + "/" + "/".join(parts) if host in DOC_HOSTS else url
    return language, version, group


def prefer_language(hits, metadata, language: str | None):
    if language is None:
        return hits
    if not LANGUAGE_TAG.fullmatch(language):
        raise ValueError("language must be a language tag")
    preferred = language.lower().split("-")[0]
    return sorted(hits, key=lambda hit: (
        (result_identity(metadata[hit.document_id].canonical_url,
                         metadata[hit.document_id].metadata_)[0] or "").split("-")[0] != preferred
    ))  # stable partition: other languages remain searchable, BM25 ties unchanged.
