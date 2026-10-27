"""Smoke test for the contract between builder.py and analyzer.py."""

from __future__ import annotations

from indexer.analyzer import analyze_index_document
from indexer.builder import calculate_index_hash, prepare_index_document


def test_document_flows_from_builder_to_analyzer(make_document, config):
    source = make_document()

    prepared = prepare_index_document(source, config=config)
    fingerprint = calculate_index_hash(prepared, config=config)
    analyzed = analyze_index_document(prepared, config=config)

    assert prepared.document_id == source.id == analyzed.document_id
    assert prepared.source_updated_at == analyzed.source_updated_at
    assert fingerprint.startswith(config.index_hash_prefix)
    assert any(f.name == "body" and f.text == prepared.body for f in analyzed.text_fields)
    assert any(
        f.name == "code_blocks" and f.text == prepared.code_blocks[0]
        for f in analyzed.code_fields
    )
