
"""Configuration for the Developer's Eye online search engine.

Environment variables use the SEARCH_ prefix.

This module does not load .env files. The application
launcher is responsible for loading the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class SearchConfigError(ValueError):
    """Invalid online search configuration."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchConfig:
    max_query_length: int = 256
    max_raw_query_length: int = 1024

    # Query planner
    default_mode: str = "all"

    # PostgreSQL FTS (must match indexer configurations)
    text_search_config: str = "english"
    code_search_config: str = "simple"

    # Retrieval and pagination
    default_limit: int = 10
    max_limit: int = 50
    max_offset: int = 1000

    # Initial snippet generation
    snippet_length: int = 240

    def __post_init__(self) -> None:
        """Reject invalid configuration before starting search."""

        positive_fields = (
            "max_query_length",
            "default_limit",
            "max_limit",
            "snippet_length",
        )

        for name in positive_fields:
            value = getattr(self, name)

            if type(value) is not int or value <= 0:
                raise SearchConfigError(
                    f"{name} must be a positive integer"
                )

        if type(self.max_offset) is not int or self.max_offset < 0:
            raise SearchConfigError(
                "max_offset must be a non-negative integer"
            )
        if (
            type(self.max_raw_query_length) is not int
            or not 1 <= self.max_raw_query_length <= 8192
        ):
            raise SearchConfigError(
                "max_raw_query_length must be between 1 and 8192"
            )

        if self.max_raw_query_length < self.max_query_length:
            raise SearchConfigError(
                "max_raw_query_length cannot be smaller than max_query_length"
            )

        if self.default_limit > self.max_limit:
            raise SearchConfigError(
                "default_limit cannot exceed max_limit"
            )

        if self.default_mode not in {"all", "text", "code"}:
            raise SearchConfigError(
                "default_mode must be all, text, or code"
            )

        for name in ("text_search_config", "code_search_config"):
            value = getattr(self, name)

            if not isinstance(value, str) or not value.strip():
                raise SearchConfigError(
                    f"{name} must be a nonempty string"
                )

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> SearchConfig:
        """Load configuration from SEARCH_* environment variables."""

        env = os.environ if environ is None else environ

        def read_int(name: str, default: int) -> int:
            raw = env.get(f"SEARCH_{name}")

            if raw is None:
                return default

            try:
                return int(raw)
            except (TypeError, ValueError) as exc:
                raise SearchConfigError(
                    f"SEARCH_{name} must be an integer"
                ) from exc

        return cls(
            max_raw_query_length=read_int("MAX_RAW_QUERY_LENGTH",1024),
            max_query_length=read_int("MAX_QUERY_LENGTH", 256),
            default_mode=env.get("SEARCH_DEFAULT_MODE", "all"),
            text_search_config=env.get(
                "SEARCH_TEXT_SEARCH_CONFIG", "english"
            ),
            code_search_config=env.get(
                "SEARCH_CODE_SEARCH_CONFIG", "simple"
            ),
            default_limit=read_int("DEFAULT_LIMIT", 10),
            max_limit=read_int("MAX_LIMIT", 50),
            max_offset=read_int("MAX_OFFSET", 1000),
            snippet_length=read_int("SNIPPET_LENGTH", 240),
        )
