
"""Configuration for the Developer's Eye retrieval vocabulary engine.

Environment prefix: VOCABULARY_

Configuration is immutable after construction.
The process launcher owns .env loading.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass

from retrieval_vocabulary.errors import VocabularyConfigError


ENV_PREFIX = "VOCABULARY_"

LOG_LEVELS = frozenset({
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
})


@dataclass(frozen=True, slots=True, kw_only=True)
class VocabularyConfig:
    """Validated configuration for vocabulary background workers."""

    batch_size: int = 100
    concurrency: int = 2
    poll_seconds: float = 10.0
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        """Validate configuration, including direct construction."""

        for name in ("batch_size", "concurrency"):
            value = getattr(self, name)

            if type(value) is not int or value < 1:
                raise VocabularyConfigError(
                    f"{name} must be a positive integer"
                )

        if (
            isinstance(self.poll_seconds, bool)
            or not isinstance(self.poll_seconds, (int, float))
            or not math.isfinite(self.poll_seconds)
            or self.poll_seconds <= 0
        ):
            raise VocabularyConfigError(
                "poll_seconds must be a positive finite number"
            )

        if not isinstance(self.log_level, str):
            raise VocabularyConfigError(
                "log_level must be a string"
            )

        normalized_level = self.log_level.strip().upper()

        if normalized_level not in LOG_LEVELS:
            raise VocabularyConfigError(
                f"log_level must be one of: "
                f"{', '.join(sorted(LOG_LEVELS))}"
            )

        object.__setattr__(
            self, "log_level", normalized_level
        )

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> VocabularyConfig:
        """Build configuration from environment variables.

        An explicit mapping can be passed for deterministic testing.
        """

        env = os.environ if environ is None else environ

        def read_int(name: str, default: int) -> int:
            key = f"{ENV_PREFIX}{name}"

            raw = env.get(key)

            if raw is None:
                return default

            if not isinstance(raw, str):
                raise VocabularyConfigError(
                    f"{key} must be a string"
                )

            try:
                return int(raw.strip())
            except ValueError as exc:
                raise VocabularyConfigError(
                    f"{key} must be an integer"
                ) from exc

        def read_float(name: str, default: float) -> float:
            key = f"{ENV_PREFIX}{name}"

            raw = env.get(key)

            if raw is None:
                return default

            if not isinstance(raw, str):
                raise VocabularyConfigError(
                    f"{key} must be a string"
                )

            try:
                return float(raw.strip())
            except ValueError as exc:
                raise VocabularyConfigError(
                    f"{key} must be a number"
                ) from exc

        log_level = env.get(
            f"{ENV_PREFIX}LOG_LEVEL", "INFO"
        )

        return cls(
            batch_size=read_int("BATCH_SIZE", 100),
            concurrency=read_int("CONCURRENCY", 2),
            poll_seconds=read_float("POLL_SECONDS", 10.0),
            log_level=log_level,
        )
