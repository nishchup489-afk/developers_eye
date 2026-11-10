"""Offline judged relevance metrics for frozen Developer's Eye ranking snapshots.

Judgments use canonical URLs rather than database IDs, which may change after
reindexing. Scores are only considered publishable when *both* top-10 lists
are fully judged and at least one independently identified relevant URL is
known (or the query is explicitly labeled as having no relevant documents).
"""

from __future__ import annotations

from math import log2
from statistics import mean
from typing import Any, Mapping

GRADE_MAX = 3
RANK_CUTOFF = 10


def _ordered_urls(report: Mapping[str, Any], rank_key: str) -> list[str]:
    rows = sorted(report["documents"], key=lambda row: row[rank_key])
    return [str(row["url"]) for row in rows]


def _positive_urls(judgments: Mapping[str, int]) -> set[str]:
    return {url for url, grade in judgments.items() if grade > 0}


def _validate_judgments(
    data: Mapping[str, Any],
) -> tuple[dict[str, int | None], bool]:
    if not isinstance(data, Mapping):
        raise ValueError("query judgments must be an object")
    grades = data.get("judgments")
    if not isinstance(grades, dict):
        raise ValueError("judgments must be a URL-to-grade object")
    no_relevant = data.get("no_relevant_documents", False)
    if type(no_relevant) is not bool:
        raise ValueError("no_relevant_documents must be boolean")
    validated: dict[str, int | None] = {}
    for url, grade in grades.items():
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError(f"invalid judgment URL: {url!r}")
        if grade is not None and (type(grade) is not int or not 0 <= grade <= GRADE_MAX):
            raise ValueError(f"grade for {url!r} must be 0..{GRADE_MAX} or null")
        validated[url] = grade
    if no_relevant and any(grade is not None and grade > 0 for grade in validated.values()):
        raise ValueError("no_relevant_documents conflicts with positive grades")
    return validated, no_relevant


def _metrics_for_order(
    urls: list[str],
    judgments: Mapping[str, int],
    *,
    positives: set[str],
    k: int,
) -> dict[str, float | None]:
    seen: set[str] = set()
    hits = 0
    first_relevant: int | None = None
    dcg = 0.0
    for rank, url in enumerate(urls[:k], start=1):
        grade = judgments.get(url, 0) if url not in seen else 0
        seen.add(url)  # Repeated canonical URLs are not new relevant results.
        if grade > 0:
            hits += 1
            if first_relevant is None:
                first_relevant = rank
        dcg += (2**grade - 1) / log2(rank + 1)

    ideal_grades = sorted(
        (judgments[url] for url in positives), reverse=True
    )[:k]
    ideal = sum((2**grade - 1) / log2(rank + 1)
                for rank, grade in enumerate(ideal_grades, start=1))
    return {
        f"precision_at_{k}": hits / k,
        f"mrr_at_{k}": (1 / first_relevant) if first_relevant else (0.0 if positives else None),
        f"ndcg_at_{k}": dcg / ideal if ideal else None,
    }


def evaluate_query(
    report: Mapping[str, Any],
    judgment_data: Mapping[str, Any],
    *,
    k: int = RANK_CUTOFF,
) -> dict[str, Any]:
    """Judge identical retrieved candidates under both ranking functions.

    Recall is *judged relevant recall* over the union of up to 100 candidates
    per channel. ALL mode may therefore contain up to 200 unique candidates.
    It is not a full-corpus recall estimate or a global top-100 recall.
    """
    if type(k) is not int or k not in (5, 10):
        raise ValueError("evaluation cutoff must be 5 or 10")
    grades, no_relevant = _validate_judgments(judgment_data)
    text_order = _ordered_urls(report, "bm25_rank")
    postgres_order = _ordered_urls(report, "postgres_rank")
    needed = set(text_order[:k]) | set(postgres_order[:k])
    missing = sorted(url for url in needed if grades.get(url) is None)

    has_unjudged = any(grade is None for grade in grades.values())
    positive_grades = {url: grade for url, grade in grades.items() if grade is not None}
    positives = _positive_urls(positive_grades)
    if not positives and not no_relevant:
        reason = "No independently confirmed positive judgments"
    elif missing or has_unjudged:
        reason = "Unjudged URLs remain"
    else:
        reason = None

    base: dict[str, Any] = {
        "query_id": report["query_id"],
        "query": report["query"],
        "mode": report["mode"],
        "candidate_count": report["candidate_count"],
        "recall_budget": "100 per channel (up to 200 in ALL mode)",
        "judged_positive_count": len(positives),
        f"missing_top_{k}_judgments": missing,
        "unjudged_count": sum(grade is None for grade in grades.values()),
    }
    if reason is not None:
        return {**base, "status": "incomplete", "reason": reason}

    # The candidate pool comes from the frozen shared BM25/PG comparison;
    # it is not a separate oracle retrieval query.
    candidates = set(text_order)
    recall = len(candidates & positives) / len(positives) if positives else None
    return {
        **base,
        "status": "complete",
        "candidate_recall_at_100_per_channel": recall,
        "bm25": _metrics_for_order(text_order, positive_grades, positives=positives, k=k),
        "postgresql": _metrics_for_order(postgres_order, positive_grades, positives=positives, k=k),
        f"bm25_top_{k}": text_order[:k],
        f"postgresql_top_{k}": postgres_order[:k],
    }


def evaluate_suite(
    snapshot: Mapping[str, Any],
    qrels: Mapping[str, Any],
    *,
    k: int = RANK_CUTOFF,
) -> dict[str, Any]:
    reports = snapshot.get("reports")
    entries = qrels.get("queries")
    if not isinstance(reports, list) or not reports:
        raise ValueError("snapshot must contain a nonempty reports list")
    if not isinstance(entries, dict):
        raise ValueError("qrels must contain a queries object")

    ids = [report["query_id"] for report in reports]
    if len(ids) != len(set(ids)) or set(entries) != set(ids):
        raise ValueError("qrel query IDs must match unique snapshot query IDs exactly")

    results = [evaluate_query(report, entries[report["query_id"]], k=k) for report in reports]
    unfinished = [r["query_id"] for r in results if r["status"] != "complete"]
    result: dict[str, Any] = {
        "status": "incomplete" if unfinished else "complete",
        "corpus_id": snapshot.get("corpus_id"),
        "snapshot_created_utc": snapshot.get("created_utc"),
        "query_count": len(results),
        "cutoff": k,
        "unjudged_query_ids": unfinished,
        "per_query": results,
        "aggregate": None,
    }
    if unfinished:
        return result

    def avg(field: str, variant: str | None = None) -> float | None:
        values = [
            r[variant][field] if variant else r[field]
            for r in results
        ]
        valid = [value for value in values if value is not None]
        return mean(valid) if valid else None

    result["aggregate"] = {
        "candidate_recall_at_100_per_channel": avg("candidate_recall_at_100_per_channel"),
        "bm25": {name: avg(name, "bm25") for name in (f"precision_at_{k}", f"mrr_at_{k}", f"ndcg_at_{k}")},
        "postgresql": {name: avg(name, "postgresql") for name in (f"precision_at_{k}", f"mrr_at_{k}", f"ndcg_at_{k}")},
        "zero_candidate_query_rate": sum(r["candidate_count"] == 0 for r in results) / len(results),
        "note": f"Macro averages exclude queries without known positive judgments from recall/MRR/nDCG. P@{k} counts missing positions as nonrelevant.",
    }
    return result


__all__ = ["evaluate_query", "evaluate_suite"]
