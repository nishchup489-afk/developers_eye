"""Independent checks for EXP-0009 metric arithmetic and labeling discipline."""
import math
import sys
from pathlib import Path

import pytest

# The scripts live in the repository-level scripts/ folder, outside the backend package.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from search_relevance_metrics.evaluate_relevance import (
    EvaluationError,
    dcg_at_k,
    evaluate,
    mrr_at_k,
    ndcg_at_k,
    pooled_recall_at_k,
    precision_at_k,
    prepare_qrels,
)


def test_precision_denominator_is_k_not_result_count():
    assert precision_at_k([1, 2], {1: 3, 2: 0}) == 0.1
    assert precision_at_k([], {}) == 0.0


def test_mrr_uses_first_relevant_rank():
    assert mrr_at_k([1, 2, 3], {1: 0, 2: 0, 3: 2}) == pytest.approx(1 / 3)
    assert mrr_at_k([1, 2, 3], {1: 0, 2: 0, 3: 0}) == 0.0


def test_dcg_and_ndcg_are_graded_and_discount_rank():
    assert dcg_at_k([3, 2], 10) == pytest.approx(7 + 3 / math.log2(3))
    assert ndcg_at_k([1, 2], {1: 3, 2: 2}) == pytest.approx(1.0)
    assert ndcg_at_k([2, 1], {1: 3, 2: 2}) < 1.0
    assert ndcg_at_k([1], {1: 0}) is None


def test_pooled_recall_is_explicitly_known_relevant_only():
    assert pooled_recall_at_k([1, 2, 3], {2: 2, 4: 3}, 2) == pytest.approx(0.5)
    assert pooled_recall_at_k([1], {1: 0}) is None


def sample_report():
    ids = list(range(1, 13))
    return {"run_id": "frozen-run", "queries": [{
        "id": "Q051", "query": "javascript fetch examples", "mode": "all",
        "bm25_order": ids,
        "postgresql_order": ids[::-1],
        "documents": [{
            "document_id": i, "title": f"Doc {i}", "url": f"https://example.org/{i}",
            "bm25_rank": i, "postgres_rank": 13 - i,
        } for i in ids],
    }]}


def test_prepare_is_union_of_both_rankings():
    rows = prepare_qrels(sample_report(), depth=10, includes=[])
    assert {int(x["document_id"]) for x in rows} == set(range(1, 13))
    assert all(x["relevance_grade"] == "" for x in rows)


def test_incomplete_labels_are_rejected():
    with pytest.raises(EvaluationError, match="unjudged"):
        evaluate(sample_report(), {"Q051": {1: 3, 2: 0}})


def test_complete_queries_produce_comparable_metrics():
    judgments = {"Q051": {i: (3 if i == 1 else 0) for i in range(1, 13)}}
    results = evaluate(sample_report(), judgments)
    assert results["query_count"] == 1
    assert results["queries"][0]["bm25"]["precision_at_10"] == pytest.approx(0.1)
    assert results["queries"][0]["bm25"]["mrr_at_10"] == 1.0
    assert results["queries"][0]["postgresql"]["mrr_at_10"] == 0.0
    assert results["queries"][0]["bm25"]["pooled_ndcg_at_10"] == 1.0
    assert results["queries"][0]["postgresql"]["pooled_ndcg_at_10"] == 0.0
