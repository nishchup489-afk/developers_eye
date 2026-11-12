"""Offline EXP-0004 CLI contracts; no database and no network required."""

from __future__ import annotations

import json
import runpy
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
SCRIPT = runpy.run_path(str(BACKEND_DIR.parent / "scripts" / "evaluate_relevance.py"))
load_queries = SCRIPT["load_queries"]
judgment_template = SCRIPT["judgment_template"]


def test_manifest_has_at_least_30_unique_stratified_queries():
    queries = load_queries(BACKEND_DIR / "evaluation" / "queries.json")
    assert len(queries) >= 30
    assert len({q["query_id"] for q in queries}) == len(queries)
    assert {"text", "code", "all"} <= {q["mode"] for q in queries}
    assert {"documentation", "identifier", "mixed", "phrase", "no-result"} <= {
        q["stratum"] for q in queries
    }


def test_judgment_template_is_blinded_and_carries_titles():
    snapshot = {
        "corpus_id": "frozen-v1",
        "reports": [{
            "query_id": "Q001", "query": "python async", "mode": "text",
            "stratum": "documentation",
            "documents": [
                {"url": "https://example.org/z", "title": "Z docs",
                 "bm25_rank": 1, "postgres_rank": 2},
                {"url": "https://example.org/a", "title": "A docs",
                 "bm25_rank": 2, "postgres_rank": 1},
            ],
        }],
    }
    template = judgment_template(snapshot)
    entry = template["queries"]["Q001"]
    assert template["corpus_id"] == "frozen-v1"
    assert entry["query"] == "python async"
    assert list(entry["judgments"]) == [
        "https://example.org/a", "https://example.org/z"
    ]
    assert entry["titles"]["https://example.org/a"] == "A docs"
    assert all(value is None for value in entry["judgments"].values())
    assert "bm25_rank" not in json.dumps(entry)
    assert "postgres_rank" not in json.dumps(entry)


def test_write_json_never_overwrites_human_judgments(tmp_path):
    write_json = SCRIPT["write_json"]
    path = tmp_path / "qrels.json"
    write_json(path, {"queries": {"Q001": {"grade": 3}}})
    try:
        write_json(path, {"queries": {}}, overwrite=False)
    except FileExistsError:
        pass
    else:
        raise AssertionError("the judging template must not overwrite user edits")
    assert json.loads(path.read_text())["queries"]["Q001"]["grade"] == 3
