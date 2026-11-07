"""EXP-0009 / Precision@10. Run this file directly for Rich demonstrations/tests.

Usage (from backend/):
    poetry run python "tests/unit/test_relavance_matrics/precision@10.py"

Human relevance grades: 0=irrelevant, 1=tangential, 2=useful, 3=excellent.
Grades 2 and 3 count as relevant. Unjudged returned results are errors.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

K = 10
RELEVANCE_THRESHOLD = 2


def precision_at_10(
    ranked_document_ids: Sequence[int],
    relevance_grades: Mapping[int, int],
) -> float:
    """Relevant returned documents / 10, even if fewer than 10 were returned."""
    if not isinstance(ranked_document_ids, Sequence) or isinstance(ranked_document_ids, (str, bytes)):
        raise TypeError("ranked_document_ids must be a sequence of integer IDs")
    if not isinstance(relevance_grades, Mapping):
        raise TypeError("relevance_grades must be a mapping")

    top = list(ranked_document_ids[:K])
    if any(type(doc_id) is not int or doc_id <= 0 for doc_id in top):
        raise ValueError("Document IDs must be positive integers")
    if len(top) != len(set(top)):
        raise ValueError("Duplicate document IDs in top 10")

    relevant = 0
    for doc_id in top:
        if doc_id not in relevance_grades:
            raise ValueError(f"Missing human relevance judgment for document {doc_id}")
        grade = relevance_grades[doc_id]
        if type(grade) is not int or not 0 <= grade <= 3:
            raise ValueError(f"Invalid relevance grade for document {doc_id}: {grade!r}")
        relevant += grade >= RELEVANCE_THRESHOLD
    return relevant / K


def run_tests() -> None:
    """Self-contained mathematical test cases, independent of search diagnostics."""
    assert precision_at_10([1, 2, 3, 4], {1: 3, 2: 2, 3: 1, 4: 0}) == 0.2
    assert precision_at_10([1, 2], {1: 3, 2: 0}) == 0.1
    assert precision_at_10([], {}) == 0.0
    assert precision_at_10(list(range(1, 11)), {i: 3 for i in range(1, 11)}) == 1.0
    assert precision_at_10(list(range(1, 12)), {i: 0 for i in range(1, 11)}) == 0.0
    for ids, grades in (([1, 1], {1: 2}), ([1], {}), ([1], {1: 4}), ([True], {True: 3})):
        try:
            precision_at_10(ids, grades)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"Expected invalid input to fail: {ids!r}")


def main() -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError as exc:
        raise SystemExit("Install rich: poetry add --group dev rich") from exc

    console = Console()
    run_tests()
    ranked = [51, 12, 15, 18, 20, 24, 31, 40, 49, 60]
    illustrative = {51: 3, 12: 0, 15: 2, 18: 0, 20: 1, 24: 0,
                    31: 3, 40: 0, 49: 2, 60: 0}
    result = precision_at_10(ranked, illustrative)
    table = Table(title="Precision@10 | Synthetic test fixture")
    table.add_column("Rank", justify="right")
    table.add_column("Document", justify="right")
    table.add_column("Human grade", justify="right")
    table.add_column("Relevant")
    for index, doc_id in enumerate(ranked, 1):
        grade = illustrative[doc_id]
        table.add_row(str(index), str(doc_id), str(grade), "YES" if grade >= 2 else "NO")
    console.print(table)
    console.print(Panel(f"P@10 = [bold green]{result:.0%}[/]\n"
                        "[dim]Demonstration data only. No real human labels are assumed.[/]\n"
                        "Self-tests: PASSED", title="EXP-0009"))


if __name__ == "__main__":
    main()
