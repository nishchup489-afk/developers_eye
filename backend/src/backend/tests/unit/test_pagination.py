"""Unit tests for candidate-pool pagination."""

import pytest

from backend.search.pagination import paginate_hits
from backend.search.types import RankedHit


def hits(total=12):
    return [RankedHit(document_id=i, score=float(total-i)) for i in range(1, total + 1)]


def test_pages_preserve_ranking():
    pool = hits()
    page = paginate_hits(pool, page=2, limit=5)
    assert [hit.document_id for hit in page.hits] == [6, 7, 8, 9, 10]
    assert page.total_candidates == 12
    assert page.total_pages == 3
    assert page.has_next and page.has_previous
    assert pool[0].document_id == 1


def test_empty_page_and_empty_pool():
    assert paginate_hits([], page=1).total_pages == 0
    result = paginate_hits(hits(2), page=3, limit=5)
    assert result.hits == ()
    assert not result.has_next


@pytest.mark.parametrize("page,limit", [(0, 5), (True, 5), (1, 0), (1, True), (1, 51), (500, 5)])
def test_invalid_args(page, limit):
    with pytest.raises(ValueError):
        paginate_hits(hits(), page=page, limit=limit)
