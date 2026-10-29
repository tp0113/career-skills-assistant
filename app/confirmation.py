"""What counts as a yes (F14). Anything not on the short list cancels the enrollment."""
import re
from typing import Any

EXPLICIT_YES = frozenset({"yes", "y", "yes please", "confirm", "yes enroll me"})


def is_explicit_yes(text: str) -> bool:
    """Lowercase, drop punctuation, squeeze spaces, then require an exact match."""
    cleaned = re.sub(r"[^a-z0-9 ]", "", text.lower())
    return " ".join(cleaned.split()) in EXPLICIT_YES


def answer_is_yes(answer: Any) -> bool:
    """The UI buttons send {"confirm": true/false}; typed replies are strings. Anything else is no."""
    if isinstance(answer, dict):
        return answer.get("confirm") is True
    if isinstance(answer, str):
        return is_explicit_yes(answer)
    return False
