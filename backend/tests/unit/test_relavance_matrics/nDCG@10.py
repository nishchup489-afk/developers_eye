"""EXP-0009 / nDCG@10. Grades 0, 1, 2, 3; gains 0, 1, 3, 7.

Run: poetry run python "tests/unit/test_relavance_matrics/ndcg@10.py"
Ideal ranking is computed over ALL supplied judged documents, not just
returned top 10; pool completeness affects interpretation.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

K = 10


def _validate_grade(grade: int) -> None:
    if type(grade) is not int or not 0 <= grade <= 3:
        raise ValueError(f"Grades must be integers in 0..3, got {grade!r}")


def dcg_at_10(grades: Sequence[int]) -> float:
    total = 0.0
    for rank, grade in enumerate(grades[:K], 1):
        _validate_grade(grade)
        total += (2 ** grade - 1) / math.log2(rank + 1)
    return total


def ndcg_at_10(
    ranked_document_ids: Sequence[int],
    relevance_grades: Mapping[int, int],
) -> float | None:
    """DCG / best DCG over judged pool; None if no positive judgments."""
    if not isinstance(ranked_document_ids, Sequence) or isinstance(ranked_document_ids, (str, bytes)):
        raise TypeError("ranked_document_ids must be a sequence of IDs")
    if not isinstance(relevance_grades, Mapping):
        raise TypeError("relevance_grades must be a mapping")
    top = list(ranked_document_ids[:K])
    if any(type(doc_id) is not int or doc_id <= 0 for doc_id in top):
        raise ValueError("Document IDs must be positive integers")
    if len(top) != len(set(top)):
        raise ValueError("Duplicate document IDs in top 10")
    for grade in relevance_grades.values():
        _validate_grade(grade)
    missing = [doc_id for doc_id in top if doc_id not in relevance_grades]
    if missing:
        raise ValueError(f"Missing judgments for top-10 documents: {missing}")
    ideal = sorted(relevance_grades.values(), reverse=True)
    idcg = dcg_at_10(ideal)
    if idcg == 0.0:
        return None
    actual = dcg_at_10([relevance_grades[doc_id] for doc_id in top])
    return min(1.0, actual / idcg)  # Protect against floating-point overshoot.


def run_tests() -> None:
    assert dcg_at_10([3, 2]) == 7 + 3 / math.log2(3)
    assert ndcg_at_10([1, 2], {1: 3, 2: 2}) == 1.0
    assert 0 < ndcg_at_10([2, 1], {1: 3, 2: 2}) < 1
    assert ndcg_at_10([3, 1, 2], {1: 3, 2: 2, 3: 0}) < 1
    assert ndcg_at_10([1], {1: 0}) is None
    assert ndcg_at_10([], {99: 3}) == 0.0
    for order, grades in (([1, 1], {1: 2}), ([1], {}), ([1], {1: -1})):
        try:
            ndcg_at_10(order, grades)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid nDCG input to fail")


def main() -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError as exc:
        raise SystemExit("Install rich: poetry add --group dev rich") from exc

    run_tests()
    graded = {1: 3, 2: 2, 3: 0}
    table = Table(title="nDCG@10 | Synthetic fixture")
    table.add_column("Ranking")
    table.add_column("nDCG@10", justify="right")
    table.add_row("Ideal: [1, 2, 3]", f"{ndcg_at_10([1, 2, 3], graded):.4f}")
    table.add_row("Worse: [2, 1, 3]", f"{ndcg_at_10([2, 1, 3], graded):.4f}")
    c = Console()
    c.print(table)
    c.print(Panel("Grades 3 and 2 receive gains 7 and 3. Earlier ranks matter more."
                  "\n[dim]Synthetic judgments; self-tests passed.[/]", title="EXP-0009"))


if __name__ == "__main__":
    main()
