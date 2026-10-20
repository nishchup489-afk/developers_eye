from dataclasses import replace

from crawler.processing.fingerprint import fingerprint_document
from crawler.processing.schemas import NormalizedDocument



first = NormalizedDocument(
    url="https://example.com/python",
    canonical_url="https://example.com/python",
    title="Python Tutorial",
    body="Python is a programming language.",
)

# Same content, different URL.
second = replace(
    first,
    url="https://mirror.example.com/python",
    canonical_url="https://mirror.example.com/python",
)

# Same URL, different content.
third = replace(
    first,
    body="Python is a powerful programming language.",
)

hash1 = fingerprint_document(first)
hash2 = fingerprint_document(second)
hash3 = fingerprint_document(third)

print(hash1 == hash2)  # True
print(hash1 == hash3)  # False
print(len(hash1))     # 64
