
from dataclasses import dataclass
from enum import StrEnum


class SearchMode(StrEnum):
    ALL = "all"
    TEXT = "text"
    CODE = "code"


class RetrievalTarget(StrEnum):
    TEXT = "text"
    CODE = "code"


@dataclass(frozen=True, slots=True)
class SearchPlan:
    query: str
    mode: SearchMode
    targets: tuple[RetrievalTarget, ...]


def _parse_mode(value: SearchMode | str) -> SearchMode:
    """Validate and normalize a requested search mode."""
    if isinstance(value, SearchMode):
        return value

    if not isinstance(value, str):
        raise TypeError("Search mode must be a string or SearchMode")

    try:
        return SearchMode(value.strip().lower())
    except ValueError as exc:
        raise ValueError(
            "Unsupported search mode. Expected: all, text, or code"
        ) from exc


def select_query_plan(
    query: str,
    *,
    mode: SearchMode | str | None = None,
    default_mode: SearchMode | str = SearchMode.ALL,
) -> SearchPlan:
    """Choose retrieval targets without executing a search."""
    if not isinstance(query, str):
        raise TypeError("Query must be a string")

    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query cannot be empty")

    selected_mode = _parse_mode(
        default_mode if mode is None else mode
    )

    if selected_mode is SearchMode.TEXT:
        targets = (RetrievalTarget.TEXT,)
    elif selected_mode is SearchMode.CODE:
        targets = (RetrievalTarget.CODE,)
    else:
        targets = (
            RetrievalTarget.TEXT,
            RetrievalTarget.CODE,
        )

    return SearchPlan(
        query=normalized_query,
        mode=selected_mode,
        targets=targets,
    )
