from dataclasses import dataclass


MAX_QUERY_TERMS = 32
MAX_TERM_CHARS = 128


@dataclass(frozen=True, slots=True)
class Snippet:
    text: str
    highlights: tuple[tuple[int, int], ...]
    truncated_start: bool
    truncated_end: bool


@dataclass(frozen=True, slots=True)
class Passage:
    text: str
    start: int
    end: int
