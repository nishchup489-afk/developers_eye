import re


_TUTORIAL_TITLE = re.compile(
    r"\b(?:tutorial|how[ -]to|step[ -]by[ -]step|getting started|walkthrough)\b",
    re.IGNORECASE,
)
_DOCUMENTATION_TITLE = re.compile(
    r"\b(?:documentation|api reference|developer reference|technical reference)\b",
    re.IGNORECASE,
)