import re


_HTML_MEDIA_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_DIRECTIVE_SPLIT = re.compile(r"[,;\s]+")
_AGENT_SCOPE = re.compile(r"^([a-z][\w-]*)\s*:\s*(.*)$", re.I)
_RETRY_AFTER_CAP_SECONDS = 86_400