
"""Production query analyzer for Developer's Eye.

Responsibilities:
    - Bound input processing costs.
    - Validate Unicode and control characters.
    - Normalize Unicode to NFC.
    - Normalize whitespace without altering quoted phrase spacing.
    - Enforce raw and normalized query length limits.
    - Return structured, safe validation errors.

PostgreSQL FTS handles tokenization, stemming and lexemes.
The retrieval layer must use parameterized SQL.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum

from backend.search.config import SearchConfig


class QueryErrorCode(StrEnum):
    EMPTY = "empty_query"
    TOO_LONG = "query_too_long"
    INVALID_UNICODE = "invalid_unicode"
    DISALLOWED_CHARACTER = "disallowed_character"


class QueryValidationError(ValueError):
    """Validation error that never includes raw user input."""

    def __init__(
        self,
        code: QueryErrorCode,
        message: str,
    ) -> None:
        self.code = code
        super().__init__(message)


# Unicode characters capable of visually reordering text.
_BIDI_CONTROLS = frozenset(
    (
        0x061C,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
    )
)

# ZWNJ and ZWJ are meaningful in some languages and emoji.
_ALLOWED_FORMAT_CONTROLS = frozenset(
    (0x200C, 0x200D)
)

_ALLOWED_CONTROL_WHITESPACE = frozenset(
    ("\t", "\n", "\r")
)


def _validate_characters(query: str) -> None:
    """Reject invalid Unicode and unsafe formatting controls."""

    for char in query:
        cp = ord(char)
        category = unicodedata.category(char)

        # Surrogates and Unicode noncharacters.
        if (
            category == "Cs"
            or 0xFDD0 <= cp <= 0xFDEF
            or (cp & 0xFFFE) == 0xFFFE
        ):
            raise QueryValidationError(
                QueryErrorCode.INVALID_UNICODE,
                "Search query contains invalid Unicode characters",
            )

        # Dangerous or invisible formatting characters.
        if (
            cp in _BIDI_CONTROLS
            or (
                category == "Cf"
                and cp not in _ALLOWED_FORMAT_CONTROLS
            )
        ):
            raise QueryValidationError(
                QueryErrorCode.DISALLOWED_CHARACTER,
                "Search query contains unsupported formatting characters",
            )

        # Reject NUL, escape sequences, DEL, etc.
        if (
            category == "Cc"
            and char not in _ALLOWED_CONTROL_WHITESPACE
        ):
            raise QueryValidationError(
                QueryErrorCode.DISALLOWED_CHARACTER,
                "Search query contains unsupported control characters",
            )


def _normalize_whitespace(query: str) -> str:
    """Normalize whitespace while preserving quoted phrase spacing.

    Outside double quotes:
        Collapse consecutive whitespace into one space.

    Inside double quotes:
        Preserve whitespace run lengths, converting individual
        whitespace characters into ASCII spaces.

    Unmatched quotes are left for the PostgreSQL query parser.
    """

    result: list[str] = []
    in_quotes = False
    pending_space = False

    for char in query:
        if char == '"':
            if pending_space and result:
                result.append(" ")

            pending_space = False
            result.append(char)
            in_quotes = not in_quotes

        elif char.isspace():
            if in_quotes:
                result.append(" ")
            else:
                pending_space = True

        else:
            if pending_space and result:
                result.append(" ")

            pending_space = False
            result.append(char)

    return "".join(result)


def analyze_query(
    raw_query: str,
    *,
    config: SearchConfig | None = None,
) -> str:
    """Validate and normalize a user search query.

    This function performs no database or network operations.

    Args:
        raw_query:
            Original query received from the client.

        config:
            Search engine configuration.

    Returns:
        Validated query preserving technical identifiers,
        case, punctuation and quoted phrases.

    Raises:
        TypeError:
            Invalid input or configuration type.

        QueryValidationError:
            Empty, oversized or invalid query.
    """

    if not isinstance(raw_query, str):
        raise TypeError(
            "Search query must be a string"
        )

    if config is None:
        config = SearchConfig()

    elif not isinstance(config, SearchConfig):
        raise TypeError(
            "config must be a SearchConfig instance"
        )

    # O(1) length check before Unicode processing.
    if len(raw_query) > config.max_raw_query_length:
        raise QueryValidationError(
            QueryErrorCode.TOO_LONG,
            "Raw search query cannot exceed "
            f"{config.max_raw_query_length} characters",
        )

    # Validate characters before normalization.
    _validate_characters(raw_query)

    # Canonical Unicode representation.
    normalized = unicodedata.normalize(
        "NFC",
        raw_query,
    )

    # Preserve quoted phrase spacing.
    normalized = _normalize_whitespace(normalized)

    if not normalized or not normalized.strip():
        raise QueryValidationError(
            QueryErrorCode.EMPTY,
            "Search query cannot be empty",
        )

    # Check the final normalized length.
    if len(normalized) > config.max_query_length:
        raise QueryValidationError(
            QueryErrorCode.TOO_LONG,
            "Search query cannot exceed "
            f"{config.max_query_length} characters",
        )

    return normalized
