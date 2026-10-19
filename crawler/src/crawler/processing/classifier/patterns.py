import re 





_TOPIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in (
        ("python", r"\bpython\b"),
        ("javascript", r"\bjavascript\b"),
        ("typescript", r"\btypescript\b"),
        ("rust", r"\brust\b"),
        ("java", r"\bjava\b"),
        ("c++", r"(?<!\w)c\+\+(?!\w)"),
        ("c#", r"(?<!\w)c#(?!\w)"),
        ("react", r"\breact(?:\.js)?\b"),
        ("nextjs", r"\bnext(?:\.js|js)\b"),
        ("fastapi", r"\bfastapi\b"),
        ("django", r"\bdjango\b"),
        ("postgresql", r"\b(?:postgres|postgresql)\b"),
        ("docker", r"\bdocker\b"),
        ("kubernetes", r"\bkubernetes\b"),
        ("aws", r"\baws\b"),
        ("redis", r"\bredis\b"),
    )
)
