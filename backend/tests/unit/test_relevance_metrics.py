"""Golden tests for the EXP-0004 evaluation metric contract (no database)."""

from __future__ import annotations

from math import log2

import pytest

from backend.search.evaluation.metrics import evaluate_query, evaluate_suite


def report(
    bm25: list[str] | None = None,
    postgres: list[str] | None = None,
) -> dict:
    bm25 = bm25 if bm25 is not None else ["https://example.org/a", "https://example.org/b", "https://example.org/d"]
    postgres = postgres if postgres is not None else ["https://example.org/d", "https://example.org/b", "https://example.org/a"]
    if set(bm25) != set(postgres):
        raise ValueError("rankers must have identical candidate IDs")
    rows = [
        {
            "url": url,
            "bm25_rank": rank,
            "postgres_rank": postgres.index(url) + 1,
        }
        for rank, url in enumerate(bm25, 1)
    ]
    return {
        "query_id": "Q001",
        "query": "python async",
        "mode": "text",
        "candidate_count": len(rows),
        "documents": rows,
    }


def qrels(**grades):
    return {"judgments": {"https://example.org/" + key: value for key, value in grades.items()},
            "no_relevant_documents": False}


def test_exact_precision_mrr_ndcg_and_candidate_recall():
    """Known-relevant c is absent from retrieval and lowers recall."""
    result = evaluate_query(report(), qrels(a=3, b=2, c=1, d=0))
    assert result["status"] == "complete"
    assert result["candidate_recall_at_100_per_channel"] == pytest.approx(2 / 3)
    assert result["bm25"]["precision_at_10"] == pytest.approx(0.2)
    assert result["postgresql"]["precision_at_10"] == pytest.approx(0.2)
    assert result["bm25"]["mrr_at_10"] == 1.0
    assert result["postgresql"]["mrr_at_10"] == 0.5

    ideal = 7 + 3 / log2(3) + 1 / log2(4)
    assert result["bm25"]["ndcg_at_10"] == pytest.approx(
        (7 + 3 / log2(3)) / ideal
    )
    assert result["postgresql"]["ndcg_at_10"] == pytest.approx(
        (3 / log2(3) + 7 / log2(4)) / ideal
    )


def test_missing_top_ten_judgments_prevent_a_published_score():
    result = evaluate_query(report(), qrels(a=3, b=2))
    assert result["status"] == "incomplete"
    assert result["missing_top_10_judgments"] == ["https://example.org/d"]
    assert "bm25" not in result


def test_ungraded_template_cannot_pass_as_irrelevant():
    result = evaluate_query(report(), qrels(a=3, b=None, d=0))
    assert result["status"] == "incomplete"
    assert result["unjudged_count"] == 1


def test_no_positive_requires_an_explicit_no_relevant_decision():
    result = evaluate_query(report(), qrels(a=0, b=0, d=0))
    assert result["status"] == "incomplete"
    no_relevant = {"judgments": qrels(a=0, b=0, d=0)["judgments"],
                   "no_relevant_documents": True}
    complete = evaluate_query(report(), no_relevant)
    assert complete["status"] == "complete"
    assert complete["candidate_recall_at_100_per_channel"] is None
    assert complete["bm25"]["mrr_at_10"] is None
    assert complete["bm25"]["ndcg_at_10"] is None
    assert complete["bm25"]["precision_at_10"] == 0


def test_duplicate_urls_do_not_count_as_multiple_relevant_documents():
    data = report(
        bm25=["https://example.org/a", "https://example.org/a", "https://example.org/d"],
        postgres=["https://example.org/d", "https://example.org/a", "https://example.org/a"],
    )
    result = evaluate_query(data, qrels(a=3, d=0))
    assert result["bm25"]["precision_at_10"] == 0.1
    assert result["bm25"]["mrr_at_10"] == 1.0
    assert result["postgresql"]["mrr_at_10"] == 0.5


@pytest.mark.parametrize("bad_grade", [True, -1, 4, 1.5, "3"])
def test_invalid_grade_is_rejected(bad_grade):
    with pytest.raises(ValueError, match="grade"):
        evaluate_query(report(), qrels(a=bad_grade, b=0, d=0))


def test_conflicting_no_relevant_flag_rejected():
    with pytest.raises(ValueError, match="conflicts"):
        evaluate_query(
            report(),
            {"judgments": qrels(a=3, b=0, d=0)["judgments"],
             "no_relevant_documents": True},
        )


def test_suite_never_reports_partial_averages_as_complete():
    snapshot = {"corpus_id": "frozen-01", "created_utc": "2026-11-06T00:00:00Z",
                "reports": [report()]}
    partial = evaluate_suite(snapshot, {"queries": {"Q001": qrels(a=3, b=0)}})
    assert partial["status"] == "incomplete" and partial["aggregate"] is None

    complete = evaluate_suite(snapshot, {"queries": {"Q001": qrels(a=3, b=2, c=1, d=0)}})
    assert complete["status"] == "complete"
    assert complete["aggregate"]["candidate_recall_at_100_per_channel"] == pytest.approx(2 / 3)
    assert complete["aggregate"]["bm25"]["mrr_at_10"] == 1


def test_suite_query_mismatch_rejected():
    with pytest.raises(ValueError, match="query IDs"):
        evaluate_suite({"reports": [report()]}, {"queries": {"Q999": qrels(a=3)}})


def test_top_five_precision_and_recall_use_the_declared_cutoff():
    result = evaluate_suite({"reports": [report()]}, {"queries": {"Q001": qrels(a=3, b=2, c=1, d=0)}}, k=5)
    assert result["cutoff"] == 5
    assert result["aggregate"]["bm25"]["precision_at_5"] == pytest.approx(2 / 5)
    assert result["aggregate"]["bm25"]["mrr_at_5"] == 1
    assert result["aggregate"]["candidate_recall_at_100_per_channel"] == pytest.approx(2 / 3)
