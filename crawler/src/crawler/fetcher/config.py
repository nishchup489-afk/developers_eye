"""Fetcher-local options; per-request security limits come from coordinator."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_CHUNK_SIZE = 16 * 1024

# The crawler fetches documents, feeds, API results, and robots.txt.
# Unknown/binary media types are deliberately not buffered into memory.
ALLOWED_MEDIA_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        "application/json",
        "application/xml",
        "text/xml",
        "application/rss+xml",
        "application/atom+xml",
        "application/feed+json",
    }
)


@dataclass(frozen=True, slots=True)
class FetcherConfig:
    chunk_size: int = DEFAULT_CHUNK_SIZE
    allowed_media_types: frozenset[str] = ALLOWED_MEDIA_TYPES

    def __post_init__(self) -> None:
        if type(self.chunk_size) is not int or self.chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if (
            not isinstance(self.allowed_media_types, frozenset)
            or not self.allowed_media_types
            or not all(isinstance(x, str) and x for x in self.allowed_media_types)
        ):
            raise ValueError("allowed_media_types must be a nonempty frozenset of MIME types")

    def permits_media_type(self, header_value: str | None) -> bool:
        if not header_value:
            return False
        media_type = header_value.split(";", 1)[0].strip().casefold()
        return (
            media_type in self.allowed_media_types
            or media_type.endswith("+json")
            or media_type.endswith("+xml")
        )
