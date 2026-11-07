"""EXP-0009 / MRR@10: Reciprocal rank of first relevant result.

Run: poetry run python "tests/unit/test_relavance_matrics/mrr@10.py"
An individual query has RR@10; MRR@10 is its mean across queries.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

K = 10
RELEVANCE_THRESHOLD = 2


def reciprocal_rank_at_10(
    ranked_document_ids: Sequence[int],
    relevance_grades: Mapping[int, int],
) -> float:
    """Return 1 / first relevant rank (1..10), or zero if none qualifies."""
    if not isinstance(ranked_document_ids, Sequence) or isinstance(ranked_document_ids, (str, bytes)):
        raise TypeError("ranked_document_ids must be a sequence of integer IDs")
    if not isinstance(relevance_grades, Mapping):
        raise TypeError("relevance_grades must be a mapping")
    top = list(ranked_document_ids[:K])
    if any(type(doc_id) is not int or doc_id <= 0 for doc_id in top):
        raise ValueError("Document IDs must be positive integers")
    if len(top) != len(set(top)):
        raise ValueError("Duplicate document IDs in top 10")
    first_relevant = None
    for index, doc_id in enumerate(top, 1):
        if doc_id not in relevance_grades:
            raise ValueError(f"Missing human relevance judgment for document {doc_id}")
        grade = relevance_grades[doc_id]
        if type(grade) is not int or not 0 <= grade <= 3:
            raise ValueError(f"Invalid relevance grade for document {doc_id}: {grade!r}")
        if first_relevant is None and grade >= RELEVANCE_THRESHOLD:
            first_relevant = index
    return 1.0 / first_relevant if first_relevant is not None else 0.0


def mean_reciprocal_rank_at_10(
    rankings: Mapping[str, Sequence[int]],
    judgments: Mapping[str, Mapping[int, int]],
) -> float | None:
    """Mean RR over queries; None when no queries were supplied."""
    if not rankings:
        return None
    values = []
    for query_id, order in rankings.items():
        if query_id not in judgments:
            raise ValueError(f"Missing judgments for query {query_id}")
        values.append(reciprocal_rank_at_10(order, judgments[query_id]))
    return sum(values) / len(values)


def run_tests() -> None:
    assert reciprocal_rank_at_10([1, 2, 3], {1: 0, 2: 1, 3: 2}) == 1 / 3
    assert reciprocal_rank_at_10([1, 2], {1: 3, 2: 0}) == 1.0
    assert reciprocal_rank_at_10([1, 2], {1: 0, 2: 1}) == 0.0
    assert reciprocal_rank_at_10([], {}) == 0.0
    assert mean_reciprocal_rank_at_10({"Q1": [1], "Q2": [2, 3]},
                                       {"Q1": {1: 3}, "Q2": {2: 0, 3: 2}}) == .75
    assert mean_reciprocal_rank_at_10({}, {}) is None
    for order, grades in (([1, 1], {1: 2}), ([1], {}), ([1], {1: 9})):
        try:
            reciprocal_rank_at_10(order, grades)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid inputs to fail")


def main() -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError as exc:
        raise SystemExit("Install rich: poetry add --group dev rich") from exc

    run_tests()
    order, grades = [1, 2, 3, 4], {1: 0, 2: 1, 3: 2, 4: 3}
    table = Table(title="Reciprocal Rank@10 | Synthetic fixture")
    table.add_column("Rank")
    table.add_column("Document")
    table.add_column("Grade")
    for rank, doc_id in enumerate(order, 1):
        table.add_row(str(rank), str(doc_id), str(grades[doc_id]))
    c = Console()
    c.print(table)
    c.print(Panel(f"RR@10 = [bold green]{reciprocal_rank_at_10(order, grades):.4f}[/]"
                  "\nFirst relevant document is at rank 3."
                  "\n[dim]Synthetic judgments; self-tests passed.[/]", title="EXP-0009"))


if __name__ == "__main__":
    main()
