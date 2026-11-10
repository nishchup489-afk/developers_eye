"""Bounded selection of relevant stored code; text remains plain, untrusted text."""
from __future__ import annotations


def code_excerpt(blocks: object, terms: tuple[str, ...], *, max_chars: int) -> str:
    if not isinstance(blocks, list) or max_chars <= 0:
        return ""
    needles = tuple(term.casefold() for term in terms if term)
    candidates = [(index, block[:max_chars]) for index, block in enumerate(blocks[:64])
                  if isinstance(block, str) and block.strip()]
    if not candidates:
        return ""
    # Prefer coverage of distinct query terms; stable ties retain source order.
    _, selected = max(candidates, key=lambda item: (
        sum(term in item[1].casefold() for term in needles), -item[0]))
    return selected
