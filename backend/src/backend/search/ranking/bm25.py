from collections.abc import Iterable

import numpy as np

from backend.search.ranking.types import BM25Parameters, ChannelStatistics 

def calculate_BM25_formula(
        N : int , # corpus.count 
        
        df: int , 
        tf: int , 
        dl: int , 
        avgdl : float , 
        k1 : float ,
        b : float 

):
    IDF_p1 = N - df + 0.5 
    IDF_p2 = df + 0.5 
    IDF_div = IDF_p1 / IDF_p2 

    IDF_per_calculation = np.log(1 + IDF_div)

    TF_p1 = (tf)*(k1 + 1)
    TF_p2 = (tf) + (k1 * (1 - b + ((b * dl)/avgdl)))
    TF_per_calculation = TF_p1/TF_p2

    return IDF_per_calculation * TF_per_calculation


def apply_BM25(
    statistics: ChannelStatistics,
    query_terms: Iterable[str],
    parameters: BM25Parameters,
) -> dict[int, float]:
    """Calculate BM25 scores for all candidate documents."""

    if not isinstance(statistics, ChannelStatistics):
        raise TypeError("statistics must be ChannelStatistics")
    if not isinstance(parameters, BM25Parameters):
        raise TypeError("parameters must be BM25Parameters")

    terms = tuple(dict.fromkeys(query_terms))

    if any(not isinstance(term, str) or not term for term in terms):
        raise ValueError("query_terms must contain nonempty lexemes")

    corpus = statistics.corpus
    scores: dict[int, float] = {} # documents : ranking 

    for document_id, document in statistics.documents.items():
        score = 0.0

        for term in terms:
            tf = document.term_frequencies.get(term, 0)

            if tf == 0:
                continue

            df = statistics.document_frequencies[term]

            score += calculate_BM25_formula(
                N=corpus.document_count,
                df=df,
                tf=tf,
                dl=document.document_length,
                avgdl=corpus.average_document_length,
                k1=parameters.k1,
                b=parameters.b,
            )

        scores[document_id] = score

    return scores
