from types import SimpleNamespace

from backend.search.presentation import prefer_language, result_identity, variant_counts


def test_translations_and_versions_share_identity_without_changing_urls():
    en = result_identity("https://fastapi.tiangolo.com/tutorial/dependencies/", {})
    pt = result_identity("https://fastapi.tiangolo.com/pt/tutorial/dependencies/", {"language": "pt-BR"})
    assert en[0] == "en" and pt[0] == "pt-br" and en[2] == pt[2]
    old = result_identity("https://docs.python.org/3.12/library/asyncio.html", {})
    new = result_identity("https://docs.python.org/3.14/library/asyncio.html", {})
    assert old[1] == "3.12" and new[1] == "3.14" and old[2] == new[2]
    assert result_identity("https://example.com/en/api", {})[2] == "https://example.com/en/api"


def test_language_preference_keeps_other_languages_and_score_order():
    hits = [SimpleNamespace(document_id=i) for i in (1, 2, 3)]
    meta = {i: SimpleNamespace(canonical_url=f"https://example.com/{i}", metadata_={"language": language})
            for i, language in enumerate(("ru", "en-US", "pt"), 1)}
    assert prefer_language(hits, meta, None) == hits
    ordered = prefer_language(hits, meta, "en")
    assert [hit.document_id for hit in ordered] == [2, 1, 3]
    assert len(ordered) == len(hits)


def test_bad_metadata_does_not_invent_language_or_version():
    assert result_identity("https://example.com/v99/", {"language": "<script>"})[:2] == (None, None)


def test_related_counts_union_translations_and_hash_copies_without_double_counting():
    hits = [SimpleNamespace(document_id=i) for i in (1, 2, 3)]
    metadata = {
        1: SimpleNamespace(canonical_url="https://fastapi.tiangolo.com/async/", metadata_={}, content_hash="a"),
        2: SimpleNamespace(canonical_url="https://fastapi.tiangolo.com/pt/async/", metadata_={}, content_hash="b"),
        3: SimpleNamespace(canonical_url="https://example.com/copy", metadata_={}, content_hash="a"),
    }
    assert variant_counts(hits, metadata) == {1: 2, 2: 1, 3: 1}
