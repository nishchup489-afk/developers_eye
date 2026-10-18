"""HTML parsing utilities for Developer's Eye.

Extract readable content and discover links from parsed HTML.
No HTTP requests or database operations.
"""

"""HTML parsing components for Developer's Eye."""

from .extractor import extract_main_content
from .metadata import extract_metadata
from .links import extract_links

__all__ = [
    "extract_main_content",
    "extract_metadata",
    "extract_links",
]