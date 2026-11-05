"""Unit tests for the BM25 formula, its data contracts and the statistics input checks.

No database: SQL behaviour of statistics.py is in tests/integration/test_retrieval.py.
"""

from __future__ import annotations

import math

import pytest

from backend.search.ranking.statistics import DocumentFrequencyCache, _consistent_corpus

from backend.search.ranking import statistics as stats_module
from backend.search.ranking.bm25 import apply_BM25, calculate_BM25_formula
from backend.search.ranking.types import (
    BM25Parameters,
    ChannelStatistics,
    CorpusStatistics,
    DocumentStatistics,
    RankingConfig,
    RankingStatistics,
)


def reference(N, df, tf, dl, avgdl, k1=1.2, b=0.75):
    """Textbook BM25 (Lucene IDF variant) written independently of bm25.py."""
    idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
    return idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))


def channel(documents, document_frequencies, *, N=10, avgdl=10.0):
    return ChannelStatistics(
        corpus=CorpusStatistics(document_count=N, average_document_length=avgdl),
        document_frequencies=document_frequencies,
        documents={
            doc_id: DocumentStatistics(document_id=doc_id, document_length=dl, term_frequencies=tf)
            for doc_id, (dl, tf) in documents.items()
        },
    )


# ---------------------------------------------------------------- formula

@pytest.mark.parametrize(
    "args",
    [
        dict(N=10, df=1, tf=1, dl=10, avgdl=10.0),
        dict(N=10, df=5, tf=3, dl=20, avgdl=10.0),
        dict(N=1000, df=999, tf=1, dl=5, avgdl=12.5),
        dict(N=3, df=3, tf=2, dl=2, avgdl=4.0, k1=2.0, b=0.0),
    ],
)
def test_formula_matches_reference(args):
    expected = reference(**args)
    args.setdefault("k1", 1.2)
    args.setdefault("b", 0.75)
    assert calculate_BM25_formula(**args) == pytest.approx(expected)


def test_rarer_terms_score_higher():
    common = calculate_BM25_formula(N=100, df=90, tf=1, dl=10, avgdl=10, k1=1.2, b=0.75)
    rare = calculate_BM25_formula(N=100, df=2, tf=1, dl=10, avgdl=10, k1=1.2, b=0.75)
    assert rare > common > 0


def test_term_frequency_saturates():
    """More occurrences score higher, but never past idf * (k1 + 1)."""
    scores = [calculate_BM25_formula(N=10, df=1, tf=tf, dl=10, avgdl=10, k1=1.2, b=0.75)
              for tf in (1, 2, 10, 1000)]
    assert scores == sorted(scores)
    idf = math.log(1 + (10 - 1 + 0.5) / 1.5)
    assert scores[-1] < idf * 2.2


def test_longer_documents_score_lower_when_b_positive():
    short = calculate_BM25_formula(N=10, df=1, tf=2, dl=5, avgdl=10, k1=1.2, b=0.75)
    long = calculate_BM25_formula(N=10, df=1, tf=2, dl=50, avgdl=10, k1=1.2, b=0.75)
    assert short > long


def test_b_zero_ignores_document_length():
    a = calculate_BM25_formula(N=10, df=1, tf=2, dl=5, avgdl=10, k1=1.2, b=0.0)
    c = calculate_BM25_formula(N=10, df=1, tf=2, dl=500, avgdl=10, k1=1.2, b=0.0)
    assert a == pytest.approx(c)


# ---------------------------------------------------------------- apply_BM25

def test_apply_scores_every_candidate_and_sums_terms():
    stats = channel({1: (10, {"python": 2, "async": 1}), 2: (10, {"python": 1}), 3: (10, {})},
                    {"python": 2, "async": 1})
    scores = apply_BM25(stats, ["python", "async"], BM25Parameters())

    assert set(scores) == {1, 2, 3}
    assert scores[1] == pytest.approx(reference(10, 2, 2, 10, 10.0) + reference(10, 1, 1, 10, 10.0))
    assert scores[2] == pytest.approx(reference(10, 2, 1, 10, 10.0))
    assert scores[3] == 0.0
    assert scores[1] > scores[2] > scores[3]


def test_apply_counts_repeated_query_terms_once():
    stats = channel({1: (10, {"python": 2})}, {"python": 1})
    once = apply_BM25(stats, ["python"], BM25Parameters())
    twice = apply_BM25(stats, ["python", "python"], BM25Parameters())
    assert once == twice


def test_apply_with_no_candidates_is_empty():
    assert apply_BM25(channel({}, {}), ["python"], BM25Parameters()) == {}


def test_apply_uses_given_parameters():
    stats = channel({1: (30, {"python": 3})}, {"python": 1})
    default = apply_BM25(stats, ["python"], BM25Parameters())[1]
    flat = apply_BM25(stats, ["python"], BM25Parameters(k1=2.0, b=0.0))[1]
    assert flat == pytest.approx(reference(10, 1, 3, 30, 10.0, k1=2.0, b=0.0))
    assert flat != pytest.approx(default)


@pytest.mark.parametrize("terms", [[""], ["python", ""], [None]])
def test_apply_rejects_invalid_terms(terms):
    with pytest.raises(ValueError, match="nonempty"):
        apply_BM25(channel({}, {}), terms, BM25Parameters())


def test_apply_rejects_wrong_argument_types():
    with pytest.raises(TypeError, match="ChannelStatistics"):
        apply_BM25({}, ["python"], BM25Parameters())
    with pytest.raises(TypeError, match="BM25Parameters"):
        apply_BM25(channel({}, {}), ["python"], {"k1": 1.2})


# ---------------------------------------------------------------- data contracts

def test_bm25_parameter_defaults():
    assert (BM25Parameters().k1, BM25Parameters().b) == (1.2, 0.75)


@pytest.mark.parametrize(
    "kwargs",
    [dict(k1=0), dict(k1=-1), dict(b=-0.1), dict(b=1.1), dict(k1=math.inf),
     dict(b=math.nan), dict(k1=True), dict(k1="1.2")],
)
def test_bm25_parameters_reject_invalid_values(kwargs):
    with pytest.raises(ValueError):
        BM25Parameters(**kwargs)


def test_ranking_config_rejects_bad_weights():
    with pytest.raises(ValueError, match="cannot be negative"):
        RankingConfig(text_weight=-1)
    with pytest.raises(ValueError, match="positive weight"):
        RankingConfig(text_weight=0, code_weight=0)
    with pytest.raises(TypeError, match="BM25Parameters"):
        RankingConfig(bm25={"k1": 1.2})
    assert RankingConfig(text_weight=0, code_weight=1).code_weight == 1


@pytest.mark.parametrize(
    "kwargs",
    [dict(document_count=-1, average_document_length=1.0),
     dict(document_count=1.5, average_document_length=1.0),
     dict(document_count=5, average_document_length=-2.0),
     dict(document_count=0, average_document_length=3.0)],
)
def test_corpus_statistics_reject_invalid_values(kwargs):
    with pytest.raises(ValueError):
        CorpusStatistics(**kwargs)


def test_document_statistics_validation_and_freezing():
    doc = DocumentStatistics(document_id=1, document_length=5, term_frequencies={"python": 2})
    with pytest.raises(TypeError):
        doc.term_frequencies["python"] = 3  # frozen mapping

    with pytest.raises(ValueError, match="document_id"):
        DocumentStatistics(document_id=0, document_length=5, term_frequencies={})
    with pytest.raises(ValueError, match="exceeds"):
        DocumentStatistics(document_id=1, document_length=2, term_frequencies={"python": 3})
    with pytest.raises(ValueError, match="invalid term"):
        DocumentStatistics(document_id=1, document_length=2, term_frequencies={" ": 1})


def test_channel_statistics_cross_checks():
    corpus = CorpusStatistics(document_count=1, average_document_length=5.0)
    doc = DocumentStatistics(document_id=1, document_length=5, term_frequencies={})
    doc2 = DocumentStatistics(document_id=2, document_length=5, term_frequencies={})

    with pytest.raises(ValueError, match="does not match"):
        ChannelStatistics(corpus=corpus, document_frequencies={}, documents={2: doc})
    with pytest.raises(ValueError, match="exceed corpus"):
        ChannelStatistics(corpus=corpus, document_frequencies={}, documents={1: doc, 2: doc2})
    with pytest.raises(ValueError, match="exceeds"):
        ChannelStatistics(corpus=corpus, document_frequencies={"python": 2}, documents={})
    with pytest.raises(ValueError, match="zero-average"):
        ChannelStatistics(corpus=CorpusStatistics(document_count=1, average_document_length=0),
                          document_frequencies={}, documents={1: doc})
    with pytest.raises(TypeError, match="DocumentStatistics"):
        ChannelStatistics(corpus=corpus, document_frequencies={}, documents={1: {"length": 5}})


def test_ranking_statistics_requires_both_channels():
    empty = channel({}, {})
    assert RankingStatistics(text=empty, code=empty).code is empty
    with pytest.raises(TypeError, match="code"):
        RankingStatistics(text=empty, code=None)


# ---------------------------------------------------------------- statistics.py input checks

@pytest.mark.parametrize("mode", ["text", "TEXT", "Code"])
def test_statistics_mode_is_case_insensitive(mode):
    assert stats_module._normalize_mode(mode) == mode.upper()


def test_statistics_mode_picks_vector_and_config():
    assert stats_module._search_config("text") == "english"
    assert stats_module._search_config("code") == "simple"
    with pytest.raises(ValueError, match="TEXT or CODE"):
        stats_module._normalize_mode("all")


@pytest.mark.parametrize("term", ["", " python", "two words", "tab\tterm", "x" * 257])
def test_statistics_reject_non_lexeme_terms(term):
    with pytest.raises(ValueError):
        stats_module._validate_term(term)


def test_statistics_term_and_id_limits():
    assert stats_module._validate_terms(["a", "b", "a"]) == ("a", "b")
    with pytest.raises(TypeError):
        stats_module._validate_terms("python")
    with pytest.raises(ValueError, match="at most"):
        stats_module._validate_terms([f"t{i}" for i in range(stats_module.MAX_QUERY_TERMS + 1)])
    with pytest.raises(ValueError, match="at most"):
        stats_module._validate_ids(range(1, stats_module.MAX_CANDIDATES + 2))
    with pytest.raises(ValueError, match="positive"):
        stats_module._validate_ids([1, 0])
    with pytest.raises(ValueError, match="positive"):
        stats_module._validate_ids([True])


def test_live_counts_above_an_old_snapshot_raise_n_instead_of_failing():
    old = CorpusStatistics(document_count=10, average_document_length=20)
    documents = {1: DocumentStatistics(document_id=1, document_length=5, term_frequencies={"python": 1})}
    corpus = _consistent_corpus(old, {"python": 12}, documents)
    assert corpus.document_count == 12
    ChannelStatistics(corpus=corpus, document_frequencies={"python": 12}, documents=documents)


def test_consistent_snapshot_is_left_alone():
    corpus = CorpusStatistics(document_count=10, average_document_length=20)
    assert _consistent_corpus(corpus, {"python": 4}, {}) is corpus


def test_empty_snapshot_with_live_documents_gets_a_usable_average():
    empty = CorpusStatistics(document_count=0, average_document_length=0)
    documents = {1: DocumentStatistics(document_id=1, document_length=8, term_frequencies={})}
    corpus = _consistent_corpus(empty, {}, documents)
    assert corpus.document_count == 1 and corpus.average_document_length == 8


def test_df_cache_expires_and_never_mixes_channels():
    cache = DocumentFrequencyCache(ttl_seconds=60)
    cache.put_many("TEXT", {"python": 3})
    assert cache.get_many("TEXT", ["python"]) == {"python": 3}
    assert cache.get_many("CODE", ["python"]) == {}
    assert DocumentFrequencyCache(ttl_seconds=-1).get_many("TEXT", ["python"]) == {}
    expired = DocumentFrequencyCache(ttl_seconds=-1)
    expired.put_many("TEXT", {"python": 3})
    assert expired.get_many("TEXT", ["python"]) == {}
