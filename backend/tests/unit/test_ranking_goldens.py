"""Golden BM25 fixture: stable document lengths, frequencies, scores, order.

Every number in GOLDEN_TEXT_SCORES was calculated independently from
log1p((N - df + .5)/(df + .5)) * tf*(k1+1) /
(tf + k1*(1-b+b*dl/avgdl)), with N=5, avgDL=10, k1=1.2, b=.75.

A ranking refactor that changes the scores must update its ADR/experiment
before updating the goldens. Database-specific tokenizer and retrieval
behavior is covered separately in tests/integration/test_ranking_developer_queries.py.
"""

from __future__ import annotations

import pytest

from backend.search.ranking.bm25 import apply_BM25
from backend.search.ranking.types import (
    BM25Parameters,
    ChannelStatistics,
    CorpusStatistics,
    DocumentStatistics,
)

# TEXT vector: (document_id, indexed length, python TF, async TF)
# Corpus size 5; each term occurs in precisely three documents.
DOCUMENTS = (
    (101, 6, 2, 2),
    (102, 10, 1, 1),
    (103, 5, 0, 3),
    (104, 20, 4, 0),
    (105, 9, 0, 0),
)
GOLDEN_TEXT_SCORES = {
    101: 1.670130002270298,
    102: 1.077993001465374,
    103: 0.9486338412895292,
    104: 0.7775687223684666,
    105: 0.0,
}
GOLDEN_TEXT_ORDER = (101, 102, 103, 104, 105)


@pytest.fixture
def fixed_channel() -> ChannelStatistics:
    return ChannelStatistics(
        corpus=CorpusStatistics(document_count=5, average_document_length=10.0),
        document_frequencies={"python": 3, "async": 3},
        documents={
            doc_id: DocumentStatistics(
                document_id=doc_id,
                document_length=length,
                term_frequencies={
                    term: freq
                    for term, freq in (("python", python_tf), ("async", async_tf))
                    if freq > 0
                },
            )
            for doc_id, length, python_tf, async_tf in DOCUMENTS
        },
    )


def test_golden_scores_and_exact_order(fixed_channel: ChannelStatistics):
    scores = apply_BM25(fixed_channel, ("python", "async"), BM25Parameters())
    assert set(scores) == set(GOLDEN_TEXT_SCORES)
    for doc_id, expected in GOLDEN_TEXT_SCORES.items():
        assert scores[doc_id] == pytest.approx(expected, abs=1e-10)
    assert tuple(sorted(scores, key=lambda doc: (-scores[doc], doc))) == GOLDEN_TEXT_ORDER


def test_duplicate_query_term_does_not_change_golden(fixed_channel: ChannelStatistics):
    once = apply_BM25(fixed_channel, ("python", "async"), BM25Parameters())
    repeated = apply_BM25(
        fixed_channel, ("python", "async", "python", "async"), BM25Parameters()
    )
    assert once == repeated


def test_single_term_golden_ties_use_document_id(fixed_channel: ChannelStatistics):
    # Both 103 and 105 score zero for python. The ordering must be stable.
    scores = apply_BM25(fixed_channel, ("python",), BM25Parameters())
    assert tuple(sorted(scores, key=lambda doc: (-scores[doc], doc))) == (
        104, 101, 102, 103, 105
    )


def test_zero_term_frequency_gives_exact_zero(fixed_channel: ChannelStatistics):
    scores = apply_BM25(fixed_channel, ("async",), BM25Parameters())
    assert scores[104] == 0.0 and scores[105] == 0.0
