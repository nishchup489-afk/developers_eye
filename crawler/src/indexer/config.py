"""Validated settings for the Developer's Eye indexer.

All settings use the INDEXER_ environment-variable prefix. This module does
not load .env files; deployment or the process launcher owns environment setup.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Callable, Mapping, TypeVar

_T = TypeVar("_T")

from indexer.errors import IndexerConfigError


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexerConfig:
    """Configuration shared by one-shot backfills and continuous index workers."""

    batch_size: int = 100
    concurrency: int = 2
    poll_seconds: float = 10.0
    index_version: int = 1
    max_document_chars: int = 1_000_000
    text_search_config: str = "english"
    code_search_config: str = "simple"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        for name, value, low, high in (
            ("batch_size", self.batch_size, 1, 10_000),
            ("concurrency", self.concurrency, 1, 128),
            ("index_version", self.index_version, 1, 999_999),
            ("max_document_chars", self.max_document_chars, 1, 10_000_000),
        ):
            if type(value) is not int or not low <= value <= high:
                raise IndexerConfigError(
                    f"{name} must be an integer between {low} and {high}"
                )

        if (
            isinstance(self.poll_seconds, bool)
            or not isinstance(self.poll_seconds, (int, float))
            or not math.isfinite(self.poll_seconds)
            or not 0 < self.poll_seconds <= 3600
        ):
            raise IndexerConfigError("poll_seconds must be finite and in (0, 3600]")

        # Names are deliberately restricted until we explicitly support other
        # PostgreSQL text-search configurations. Never interpolate raw input
        # into SQL identifiers or expressions.
        allowed_configs = {"english", "simple"}
        for name in ("text_search_config", "code_search_config"):
            value = getattr(self, name)
            if not isinstance(value, str) or value not in allowed_configs:
                raise IndexerConfigError(
                    f"{name} must be one of: {', '.join(sorted(allowed_configs))}"
                )

        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise IndexerConfigError(
                "log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )

    @property
    def index_hash_prefix(self) -> str:
        """Prefix for indexed_hash, e.g. v1:<sha256>, without a new DB column."""
        return f"v{self.index_version}:"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> IndexerConfig:
        """Read settings from INDEXER_* variables; reject malformed values."""
        source = os.environ if environ is None else environ
        defaults = cls()

        def read(name: str, cast: Callable[[str], _T], default: _T) -> _T:
            key = f"INDEXER_{name}"
            raw = source.get(key)
            if raw is None:
                return default
            if not isinstance(raw, str) or not raw.strip():
                raise IndexerConfigError(f"{key} must not be empty")
            try:
                return cast(raw.strip())
            except (TypeError, ValueError, OverflowError) as exc:
                raise IndexerConfigError(
                    f"{key} has invalid value: {raw!r}"
                ) from exc

        return cls(
            batch_size=read("BATCH_SIZE", int, defaults.batch_size),
            concurrency=read("CONCURRENCY", int, defaults.concurrency),
            poll_seconds=read("POLL_SECONDS", float, defaults.poll_seconds),
            index_version=read("INDEX_VERSION", int, defaults.index_version),
            max_document_chars=read(
                "MAX_DOCUMENT_CHARS", int, defaults.max_document_chars
            ),
            text_search_config=read(
                "TEXT_SEARCH_CONFIG", str, defaults.text_search_config
            ).lower(),
            code_search_config=read(
                "CODE_SEARCH_CONFIG", str, defaults.code_search_config
            ).lower(),
            log_level=read("LOG_LEVEL", str, defaults.log_level).upper(),
        )
