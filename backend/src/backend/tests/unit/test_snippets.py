"""Behavioral tests for Developer's Eye's pure-Python snippet engine."""

from __future__ import annotations

import pytest

from backend.search.snippets import (
    MAX_QUERY_TERMS,
    MAX_TERM_CHARS,
    Passage,
    Snippet,
    find_candidate_passages,
    find_highlight_spans,
    generate_snippet,
    normalize_snippet_text,
    score_passage,
)


class TestNormalizeSnippetText:
    def test_collapses_prose_whitespace(self) -> None:
        assert normalize_snippet_text("  FastAPI  \n\t async  ") == "FastAPI async"

    def test_normalizes_windows_and_old_mac_line_endings(self) -> None:
        assert normalize_snippet_text("A\r\nB\rC") == "A B C"

    def test_unicode_nfc(self) -> None:
        assert normalize_snippet_text("Cafe\u0301") == "Café"

    def test_preserves_code_indentation_and_line_breaks(self) -> None:
        code = "\n  async def run():\r\n      return 1\r\n"
        assert normalize_snippet_text(code, preserve_code=True) == (
            "  async def run():\n      return 1"
        )

    @pytest.mark.parametrize("text", ["", "  \n  "])
    def test_blank_prose_is_empty(self, text: str) -> None:
        assert normalize_snippet_text(text) == ""

    def test_whitespace_only_code_is_empty(self) -> None:
        assert normalize_snippet_text(" \n \t", preserve_code=True) == ""

    @pytest.mark.parametrize("bad", [None, 2, [], b"bytes"])
    def test_invalid_input_type(self, bad: object) -> None:
        with pytest.raises(TypeError, match="text must be a string"):
            normalize_snippet_text(bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [None, 0, "yes"])
    def test_invalid_preserve_code(self, bad: object) -> None:
        with pytest.raises(TypeError, match="preserve_code must be a boolean"):
            normalize_snippet_text("text", preserve_code=bad)  # type: ignore[arg-type]


class TestHighlightSpans:
    def test_exact_offsets_are_end_exclusive(self) -> None:
        assert find_highlight_spans("FastAPI async", ("FastAPI", "async")) == (
            (0, 7), (8, 13)
        )

    def test_case_insensitive(self) -> None:
        assert find_highlight_spans("FASTAPI fastapi", ["FastAPI"]) == (
            (0, 7), (8, 15)
        )

    def test_no_partial_word_matches(self) -> None:
        assert find_highlight_spans("go google go", ["go"]) == (
            (0, 2), (10, 12)
        )

    def test_longer_overlapping_term_takes_priority(self) -> None:
        assert find_highlight_spans("async def run", ["async", "async def"]) == (
            (0, 9),
        )

    def test_regex_punctuation_is_literal(self) -> None:
        assert find_highlight_spans("Use C++ with (x+y).", ["C++", "(x+y)"]) == (
            (4, 7), (13, 18)
        )

    def test_no_terms_returns_empty_tuple(self) -> None:
        assert find_highlight_spans("python", []) == ()

    def test_nonmatching_terms_return_empty(self) -> None:
        assert find_highlight_spans("FastAPI", ["django"]) == ()

    def test_duplicate_terms_do_not_duplicate_spans(self) -> None:
        assert find_highlight_spans("Python python", ["Python", "python"]) == (
            (0, 6), (7, 13)
        )

    def test_highlights_index_unicode_codepoints(self) -> None:
        assert find_highlight_spans("🐍 python", ["python"]) == ((2, 8),)

    @pytest.mark.parametrize("bad", ["python", b"python", None, 7])
    def test_query_terms_must_be_iterable_of_strings(self, bad: object) -> None:
        with pytest.raises(TypeError):
            find_highlight_spans("python", bad)  # type: ignore[arg-type]

    def test_rejects_nonstring_term(self) -> None:
        with pytest.raises(TypeError, match="each query term"):
            find_highlight_spans("python", ["python", 123])  # type: ignore[list-item]

    def test_ignores_empty_terms(self) -> None:
        assert find_highlight_spans("Python", ["  ", "Python"]) == ((0, 6),)

    def test_rejects_term_too_long(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed"):
            find_highlight_spans("x", ["a" * (MAX_TERM_CHARS + 1)])

    def test_accepts_maximum_unique_terms(self) -> None:
        terms = [f"term{i}" for i in range(MAX_QUERY_TERMS)]
        assert find_highlight_spans("term0", terms) == ((0, 5),)

    def test_rejects_too_many_unique_terms(self) -> None:
        terms = [f"term{i}" for i in range(MAX_QUERY_TERMS + 1)]
        with pytest.raises(ValueError, match="unique terms"):
            find_highlight_spans("term0", terms)


class TestPassageScore:
    def test_zero_for_nonmatches(self) -> None:
        assert score_passage("FastAPI tutorial", ["django"]) == 0

    def test_zero_for_no_query_terms(self) -> None:
        assert score_passage("FastAPI tutorial", []) == 0

    def test_distinct_query_term_coverage_is_rewarded(self) -> None:
        assert score_passage("python python python python", ["python", "async"]) == 7
        assert score_passage("python async", ["python", "async"]) == 10

    def test_repeat_bonus_is_capped_at_three(self) -> None:
        assert score_passage("python " * 15, ["python"]) == 7

    def test_literal_punctuation_query(self) -> None:
        assert score_passage("C++ examples", ["C++"]) == 5

    def test_invalid_passage_rejected(self) -> None:
        with pytest.raises(TypeError, match="passage"):
            score_passage(None, ["python"])  # type: ignore[arg-type]


class TestCandidatePassages:
    def test_short_document_returns_full_passage(self) -> None:
        text = "FastAPI async database"
        assert find_candidate_passages(text, ["async"]) == (
            Passage(text, 0, len(text)),
        )

    def test_extracts_match_near_end(self) -> None:
        text = "Overview " + "irrelevant " * 45 + "async database FastAPI"
        passages = find_candidate_passages(text, ["async", "database"], max_chars=90)
        assert passages
        assert "async" in passages[0].text
        assert passages[0].start > 0
        assert len(passages[0].text) <= 90

    def test_candidates_are_sorted_by_relevance(self) -> None:
        text = (
            "python framework overview "
            + "general information " * 15
            + "python async database examples "
            + "reference details " * 15
        )
        passages = find_candidate_passages(
            text,
            ["python", "async", "database"],
            max_chars=90,
        )
        assert passages
        scores = [
            score_passage(p.text, ["python", "async", "database"])
            for p in passages
        ]
        assert scores == sorted(scores, reverse=True)
        assert "async" in passages[0].text
        assert "database" in passages[0].text

    def test_candidates_match_original_normalized_text_slices(self) -> None:
        text = "one   two  " + "other stuff " * 20 + " python   async "
        normalized = normalize_snippet_text(text)
        passages = find_candidate_passages(text, ["python"], max_chars=70)
        assert passages
        assert all(normalized[p.start:p.end] == p.text for p in passages)

    def test_no_match_returns_prefix(self) -> None:
        text = "z" * 300
        assert find_candidate_passages(text, ["python"], max_chars=40) == ()

    def test_no_terms_returns_prefix(self) -> None:
        text = "x" * 300
        assert find_candidate_passages(text, [], max_chars=40) == (
            Passage("x" * 40, 0, 40),
        )

    def test_empty_content_returns_no_passages(self) -> None:
        assert find_candidate_passages("", ["python"]) == ()

    def test_candidate_count_is_capped(self) -> None:
        text = ("python " + "z" * 100) * 20
        passages = find_candidate_passages(
            text, ["python"], max_chars=50, max_candidates=2
        )
        assert len(passages) <= 2

    @pytest.mark.parametrize("bad", [0, -1, True, 1.5])
    def test_invalid_max_chars(self, bad: object) -> None:
        with pytest.raises(ValueError, match="max_chars"):
            find_candidate_passages("python", ["python"], max_chars=bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [0, -1, True, 2.0])
    def test_invalid_max_candidates(self, bad: object) -> None:
        with pytest.raises(ValueError, match="max_candidates"):
            find_candidate_passages(
                "python", ["python"], max_candidates=bad  # type: ignore[arg-type]
            )


class TestGenerateSnippet:
    def test_short_document_is_complete_and_highlighted(self) -> None:
        snippet = generate_snippet("FastAPI async database", ["fastapi", "async"])
        assert snippet == Snippet(
            text="FastAPI async database",
            highlights=((0, 7), (8, 13)),
            truncated_start=False,
            truncated_end=False,
        )

    def test_middle_match_selects_relevant_window(self) -> None:
        text = "intro " + "unrelated " * 18 + "FastAPI async database " + "end " * 24
        snippet = generate_snippet(text, ["async", "database"], max_chars=70)
        assert "async database" in snippet.text
        assert snippet.truncated_start
        assert snippet.truncated_end
        assert len(snippet.text) <= 70

    def test_no_match_falls_back_to_description(self) -> None:
        snippet = generate_snippet(
            "The full body talks about databases.",
            ["nonexistent"],
            description="  Concise   document description. ",
        )
        assert snippet.text == "Concise document description."
        assert snippet.highlights == ()
        assert not snippet.truncated_start
        assert not snippet.truncated_end

    def test_no_match_without_description_uses_document_prefix(self) -> None:
        snippet = generate_snippet("The start of a very long document.", ["python"], max_chars=10)
        assert snippet.text == "The start "
        assert snippet.truncated_end
        assert not snippet.truncated_start

    def test_empty_body_uses_description(self) -> None:
        snippet = generate_snippet("", ["python"], description="Some description")
        assert snippet.text == "Some description"

    def test_empty_body_and_description(self) -> None:
        assert generate_snippet("", ["python"]) == Snippet("", (), False, False)

    def test_empty_terms_uses_description_fallback(self) -> None:
        snippet = generate_snippet("A paragraph.", [], description="Description")
        assert snippet.text == "Description"

    def test_description_cannot_override_body_match(self) -> None:
        snippet = generate_snippet("python reference", ["python"], description="Other description")
        assert snippet.text == "python reference"

    def test_descriptions_are_limited(self) -> None:
        snippet = generate_snippet("", ["unmatched"], description="d" * 120, max_chars=30)
        assert len(snippet.text) == 30
        assert snippet.truncated_end

    def test_code_mode_preserves_indentation(self) -> None:
        snippet = generate_snippet(
            "async def run():\n    return 42",
            ["async"],
            preserve_code=True,
        )
        assert snippet.text == "async def run():\n    return 42"

    def test_unicode_nfc_normalized_before_matching(self) -> None:
        snippet = generate_snippet("A Cafe\u0301 serves coffee", ["Café"])
        assert snippet.text == "A Café serves coffee"
        assert snippet.highlights == ((2, 6),)

    def test_contains_html_as_plain_text(self) -> None:
        source = "<script>alert(1)</script> FastAPI"
        snippet = generate_snippet(source, ["FastAPI"])
        assert snippet.text == source
        assert "<script>" in snippet.text

    def test_one_shot_query_terms_generator(self) -> None:
        terms = (word for word in ("python", "async"))
        snippet = generate_snippet("python async", terms)
        assert snippet.highlights == ((0, 6), (7, 12))

    def test_snippet_is_immutable(self) -> None:
        snippet = generate_snippet("python", ["python"])
        with pytest.raises(AttributeError):
            snippet.text = "django"  # type: ignore[misc]

    @pytest.mark.parametrize("bad", [0, -1, True, 1.5])
    def test_invalid_max_chars(self, bad: object) -> None:
        with pytest.raises(ValueError, match="max_chars"):
            generate_snippet("python", ["python"], max_chars=bad)  # type: ignore[arg-type]

    def test_invalid_description_type(self) -> None:
        with pytest.raises(TypeError, match="description"):
            generate_snippet("python", ["python"], description=42)  # type: ignore[arg-type]

    def test_nonstring_body(self) -> None:
        with pytest.raises(TypeError, match="text"):
            generate_snippet(None, ["python"])  # type: ignore[arg-type]

    def test_highlights_are_within_final_snippet(self) -> None:
        text = "irrelevant " * 100 + "async python fastapi" + " other " * 100
        snippet = generate_snippet(text, ["async", "python", "fastapi"], max_chars=85)
        assert all(
            0 <= start < end <= len(snippet.text)
            for start, end in snippet.highlights
        )
        for start, end in snippet.highlights:
            assert snippet.text[start:end].casefold() in {"async", "python", "fastapi"}
