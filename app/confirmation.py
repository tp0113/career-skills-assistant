"""What counts as a yes (F14). Anything not on the short list cancels the enrollment."""
import re
from typing import Any

EXPLICIT_YES = frozenset({"yes", "y", "yes please", "confirm", "yes enroll me"})


def is_explicit_yes(text: str) -> bool:
    """Lowercase, drop only . , ! and squeeze spaces, then require an exact match.

    Only those three marks are removed. Any other character stays, so extra words in any
    language ("yes, 但不要报名" = "yes, but don't enroll") make it a no instead of vanishing.
    """
    cleaned = re.sub(r"[.,!]", "", text.lower())
    return " ".join(cleaned.split()) in EXPLICIT_YES


def answer_is_yes(answer: Any, pending_course_id: str) -> bool:
    """The UI buttons send {"confirm": true/false, "course_id": ...}; typed replies are strings.

    A button press counts only for the course it was shown for, so a stale click cannot
    confirm a newer proposal. Anything else is no.
    """
    if isinstance(answer, dict):
        return answer.get("confirm") is True and answer.get("course_id") == pending_course_id
    if isinstance(answer, str):
        return is_explicit_yes(answer)
    return False
