from __future__ import annotations

import pytest
from backend.search.query_analyzer.analyzer import (
    QueryErrorCode,
    QueryValidationError,
    analyze_query,
)
from backend.search.config import SearchConfig, SearchConfigError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("python", "python"),
        (" FastAPI    async   Python ", "FastAPI async Python"),
        ("python\nasyncio", "python asyncio"),
        ("python\tasyncio", "python asyncio"),
        ("python\u2003asyncio", "python asyncio"),
        ('python   "async    def"   tutorial', 'python "async    def" tutorial'),
        ('  "  async def  "  ', '"  async def  "'),
        ('"async\t\tdef"', '"async  def"'),
        ("C++", "C++"),
        ("C#", "C#"),
        ("useState()", "useState()"),
        ("std::vector<T>", "std::vector<T>"),
        ("--version", "--version"),
        ("'single  quotes'", "'single quotes'"),
        ('"unclosed    quote', '"unclosed    quote'),
        ("Cafe\u0301", "Café"),
        ("नमस्ते", "नमस्ते"),
        ("👩\u200d💻", "👩\u200d💻"),
        ("x" * 256, "x" * 256),
    ],
)
def test_valid_queries(raw: str, expected: str) -> None:
    assert analyze_query(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "\n\t", "\u2003"])
def test_empty_queries(raw: str) -> None:
    with pytest.raises(QueryValidationError) as exc:
        analyze_query(raw)
    assert exc.value.code is QueryErrorCode.EMPTY


@pytest.mark.parametrize(
    "raw",
    ["\x00", "hello\x7fworld", "\x1b[31m", "one\x0btwo", "one\x85two",
     "bad\ud800surrogate", "bad\udfff", "a\ufdd0", "a\ufffe", "a\U0010ffff"],
)
def test_disallowed_controls(raw: str) -> None:
    with pytest.raises(QueryValidationError) as exc:
        analyze_query(raw)
    assert exc.value.code in {
        QueryErrorCode.INVALID_UNICODE,
        QueryErrorCode.DISALLOWED_CHARACTER,
    }
    assert raw not in str(exc.value)


@pytest.mark.parametrize("cp", [0x061C, 0x200E, 0x200F, 0x202E, 0x2066, 0x2069, 0x200B, 0x2060, 0xFEFF, 0x00AD])
def test_rejects_unsafe_format_controls(cp: int) -> None:
    with pytest.raises(QueryValidationError) as exc:
        analyze_query(f"foo{chr(cp)}bar")
    assert exc.value.code is QueryErrorCode.DISALLOWED_CHARACTER


def test_normalized_length_rejected() -> None:
    with pytest.raises(QueryValidationError) as exc:
        analyze_query("x" * 257)
    assert exc.value.code is QueryErrorCode.TOO_LONG


def test_raw_length_checked_before_scan() -> None:
    with pytest.raises(QueryValidationError) as exc:
        analyze_query("\x00" + " " * 1024)
    assert exc.value.code is QueryErrorCode.TOO_LONG


def test_extra_whitespace_within_raw_limit() -> None:
    assert analyze_query(" " * 500 + "python" + " " * 500) == "python"


def test_custom_config() -> None:
    config = SearchConfig(max_query_length=8, max_raw_query_length=16)
    assert analyze_query("  python  ", config=config) == "python"
    with pytest.raises(QueryValidationError) as exc:
        analyze_query("a" * 9, config=config)
    assert exc.value.code is QueryErrorCode.TOO_LONG


@pytest.mark.parametrize("raw", [None, 1, {}, [], True, b"python"])
def test_rejects_nonstrings(raw: object) -> None:
    with pytest.raises(TypeError):
        analyze_query(raw)


def test_rejects_nonconfig() -> None:
    with pytest.raises(TypeError):
        analyze_query("python", config="bad")


def test_config_rejects_invalid_raw_limits() -> None:
    with pytest.raises(SearchConfigError):
        SearchConfig(max_query_length=256, max_raw_query_length=255)
    with pytest.raises(SearchConfigError):
        SearchConfig(max_query_length=4097)
    with pytest.raises(SearchConfigError):
        SearchConfig(max_raw_query_length=16385)


def test_config_read_from_env() -> None:
    config = SearchConfig.from_env({"SEARCH_MAX_QUERY_LENGTH": "512", "SEARCH_MAX_RAW_QUERY_LENGTH": "2048"})
    assert config.max_query_length == 512
    assert config.max_raw_query_length == 2048


def test_invalid_env() -> None:
    with pytest.raises(SearchConfigError):
        SearchConfig.from_env({"SEARCH_MAX_RAW_QUERY_LENGTH": "nope"})
