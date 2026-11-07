"""EXP-0009 / Known-relevant Recall@100 (NOT exhaustive corpus recall).

Run: poetry run python "tests/unit/test_relavance_matrics/recall@100.py"

The denominator is independently known relevant documents in the qrels pool.
To estimate full corpus Recall@100, independently find and judge documents
outside the search engine's retrieved candidate pool.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

K = 100
RELEVANCE_THRESHOLD = 2


def known_relevant_recall_at_100(
    ranked_document_ids: Sequence[int],
    relevance_grades: Mapping[int, int],
) -> float | None:
    """Fraction of known-relevant documents found in the first 100 results."""
    if not isinstance(ranked_document_ids, Sequence) or isinstance(ranked_document_ids, (str, bytes)):
        raise TypeError("ranked_document_ids must be a sequence of IDs")
    if not isinstance(relevance_grades, Mapping):
        raise TypeError("relevance_grades must be a mapping")
    ids = list(ranked_document_ids[:K])
    if any(type(doc_id) is not int or doc_id <= 0 for doc_id in ids):
        raise ValueError("Document IDs must be positive integers")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate document IDs in top 100")
    relevant = set()
    for doc_id, grade in relevance_grades.items():
        if type(doc_id) is not int or doc_id <= 0:
            raise ValueError(f"Invalid judged document ID {doc_id!r}")
        if type(grade) is not int or not 0 <= grade <= 3:
            raise ValueError(f"Invalid grade for {doc_id}: {grade!r}")
        if grade >= RELEVANCE_THRESHOLD:
            relevant.add(doc_id)
    if not relevant:
        return None
    return len(set(ids) & relevant) / len(relevant)


def run_tests() -> None:
    assert known_relevant_recall_at_100([1, 2, 3], {2: 2, 4: 3}) == 0.5
    assert known_relevant_recall_at_100([1, 2, 3], {1: 2, 2: 3}) == 1.0
    assert known_relevant_recall_at_100([], {1: 3}) == 0.0
    assert known_relevant_recall_at_100([1], {1: 0}) is None
    assert known_relevant_recall_at_100(list(range(1, 102)), {101: 3}) == 0.0
    for ids, grades in (([1, 1], {1: 2}), ([1], {1: 4}), ([1], {True: 2})):
        try:
            known_relevant_recall_at_100(ids, grades)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid input to fail")


def main() -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError as exc:
        raise SystemExit("Install rich: poetry add --group dev rich") from exc

    run_tests()
    known = {2: 2, 4: 3}
    results = [1, 2, 3]
    table = Table(title="Known-relevant Recall@100 | Synthetic fixture")
    table.add_column("Known relevant IDs")
    table.add_column("Returned IDs")
    table.add_column("Found")
    table.add_row("2, 4", "1, 2, 3", "2")
    c = Console()
    c.print(table)
    c.print(Panel(f"Known-relevant recall@100: [bold green]{known_relevant_recall_at_100(results, known):.0%}[/]"
                  "\n[bold yellow]Not exhaustive Recall@100.[/]"
                  "\n[dim]Synthetic judgments; self-tests passed.[/]", title="EXP-0009"))


if __name__ == "__main__":
    main()
