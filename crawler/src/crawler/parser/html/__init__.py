"""HTML parsing utilities for Developer's Eye.

Extract readable content and discover links from parsed HTML.
No HTTP requests or database operations.
"""

from .extractor import ExtractedContent, extract_main_content
from .links import find_links
from .metadata import extract_metadata , ExtractedMetadata

__all__ = [
    "ExtractedContent",
    "extract_main_content",
    "find_links",
    "ExtractedMetadata",
    "extract_metadata"
]