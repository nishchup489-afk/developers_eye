import re
from typing import Iterable
import unicodedata

from backend.search.snippets.types import MAX_QUERY_TERMS, MAX_TERM_CHARS


def _positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def normalize_snippet_text(
    text: str,
    *,
    preserve_code: bool = False,
) -> str:
    """Normalize prose while preserving code indentation when requested."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not isinstance(preserve_code, bool):
        raise TypeError("preserve_code must be a boolean")

    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if preserve_code:
        return text.strip("\n") if text.strip() else ""

    return " ".join(text.split())


def _normalize_terms(terms: Iterable[str]) -> tuple[str, ...]:
    """Validate, normalize, and deduplicate query terms."""
    if isinstance(terms, (str, bytes)):
        raise TypeError(
            "query_terms must be an iterable of terms, not a string"
        )

    try:
        iterator = iter(terms)
    except TypeError as exc:
        raise TypeError("query_terms must be iterable") from exc

    result: list[str] = []
    seen: set[str] = set()

    for term in iterator:
        if not isinstance(term, str):
            raise TypeError("each query term must be a string")

        normalized = normalize_snippet_text(term)

        if not normalized:
            continue

        if len(normalized) > MAX_TERM_CHARS:
            raise ValueError(
                f"query terms cannot exceed {MAX_TERM_CHARS} characters"
            )

        folded = normalized.casefold()

        if folded not in seen:
            seen.add(folded)
            result.append(normalized)

            if len(result) > MAX_QUERY_TERMS:
                raise ValueError(
                    f"query_terms cannot contain more than "
                    f"{MAX_QUERY_TERMS} unique terms"
                )

    return tuple(result)


def _pattern(
    terms: tuple[str, ...],
) -> re.Pattern[str] | None:
    """Compile case-insensitive matches with appropriate word boundaries."""
    if not terms:
        return None

    alternatives = []

    for i, term in enumerate(
        sorted(terms, key=len, reverse=True)
    ):
        prefix = (
            r"(?<!\w)"
            if re.match(r"\w", term[0])
            else ""
        )

        suffix = (
            r"(?!\w)"
            if re.match(r"\w", term[-1])
            else ""
        )

        alternatives.append(
            f"(?P<t{i}>{prefix}{re.escape(term)}{suffix})"
        )

    return re.compile(
        "|".join(alternatives),
        re.IGNORECASE,
    )

