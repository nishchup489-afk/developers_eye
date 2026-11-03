import pytest

from backend.search.snippets import generate_snippet, find_candidate_passages


@pytest.mark.parametrize("preserve_code", [False, True])
@pytest.mark.parametrize("budget", [1, 8, 20, 40, 80])
def test_snippet_never_exceeds_character_budget(preserve_code, budget):
    text = "prefix " * 12 + "needle\n" + "long_line_of_code = 1234567890\n" * 8
    snippet = generate_snippet(
        text, ["needle"], max_chars=budget, preserve_code=preserve_code
    )
    assert len(snippet.text) <= budget
    assert all(0 <= start < end <= len(snippet.text) for start, end in snippet.highlights)


@pytest.mark.parametrize("preserve_code", [False, True])
def test_candidate_windows_respect_budget(preserve_code):
    text = "x" * 30 + "\nneedle\n" + "y" * 80
    candidates = find_candidate_passages(
        text, ["needle"], max_chars=35, preserve_code=preserve_code
    )
    assert candidates
    assert all(len(p.text) <= 35 for p in candidates)


def test_fallback_description_is_bounded():
    snippet = generate_snippet(
        "unrelated", ["needle"], description="description " * 20, max_chars=17
    )
    assert len(snippet.text) <= 17
    assert snippet.highlights == ()
