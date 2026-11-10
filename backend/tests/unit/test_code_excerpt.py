from backend.search.snippets.code import code_excerpt


def test_later_code_block_with_more_query_terms_beats_first_block():
    blocks = ["import asyncio", "asyncio.create_task(fetch(url))", "asyncio.run(main())"]
    assert code_excerpt(blocks, ("create_task", "fetch"), max_chars=100) == blocks[1]


def test_code_keeps_indentation_and_is_bounded():
    text = "    await fetch(url)\n" * 20
    assert code_excerpt([text], ("fetch",), max_chars=40) == text[:40]
    assert code_excerpt([None, "", "pass"], (), max_chars=10) == "pass"


def test_invalid_blocks_do_not_prevent_plain_body_fallback():
    assert code_excerpt(None, ("fetch",), max_chars=100) == ""
    assert code_excerpt(["pass"], (), max_chars=0) == ""
