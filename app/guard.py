"""Privacy guard: a deterministic check that runs before any model call.

Why code and not a prompt: a refused message never reaches the model, so another person's data
cannot leak through it. The tools also cannot return anyone else's data (they take no employee id).
Known limitation: an uncapitalized outside name with no possessive ("what does daniel know") is
not caught. Nothing leaks in that case, because no tool can look that person up.
"""
import re

from app.data import Catalog, Employee
from app.prompts import REFUSAL
from app.session import Session

# Rule 3: relationship and group phrases.
_GROUP_PHRASES = re.compile(
    r"\b(?:my\s+(?:manager|boss|lead|colleagues?|coworkers?|teammates?|team|peers?|direct\s+reports?)"
    r"|everyone|everybody|all\s+employees|other\s+employees|other\s+people"
    r"|someone\s+else|anyone\s+else)\b",
    re.IGNORECASE,
)
# Rule 2: a capitalized word followed by 's.
_POSSESSIVE = re.compile(r"\b([A-Z][a-z]+)'s\b")
# Rule 4: "I'm X", "I am X", "this is X" (one or two words after).
_IDENTITY = re.compile(r"\b(?:i'm|i\s+am|this\s+is)\s+([a-z]+(?:\s+[a-z]+)?)", re.IGNORECASE)

# Common capitalized words that can legitimately be followed by 's.
_COMMON_WORDS = {
    "what", "that", "it", "there", "here", "let", "who", "today", "how", "where", "when",
    "why", "which", "he", "she", "this", "one", "everything", "something", "nothing", "name",
}


def _normalize(message: str) -> str:
    """Treat curly apostrophes like straight ones so "Daniel’s" cannot slip past."""
    return message.replace("’", "'").replace("‘", "'")


def _name_parts(employee: Employee) -> list[str]:
    return [employee.name, *employee.name.split()]


def _others(catalog: Catalog, session: Session) -> list[Employee]:
    return [e for e in catalog.employees.values() if e.id != session.employee_id]


def _word_in(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) is not None


def _mentions_other_employee(text: str, others: list[Employee]) -> bool:
    """Rule 1: full, first or last name of someone else. `\b` also matches before 's."""
    return any(_word_in(text, part) for e in others for part in _name_parts(e))


def _allowed_possessives(catalog: Catalog, me: Employee) -> set[str]:
    """Rule 2 allowlist: common words, my own first name, and every word in skill and course names."""
    allowed = set(_COMMON_WORDS) | {me.name.split()[0].lower()}
    for skill in catalog.skills.values():
        allowed.update(re.findall(r"[a-z]+", skill.name.lower()))
    for course in catalog.courses.values():
        allowed.update(re.findall(r"[a-z]+", course.title.lower()))
    return allowed


def _has_foreign_possessive(text: str, allowed: set[str]) -> bool:
    return any(word.lower() not in allowed for word in _POSSESSIVE.findall(text))


def _claims_to_be_other(text: str, others: list[Employee]) -> bool:
    """Rule 4: "I'm Marcus" when signed in as someone else."""
    for claimed in _IDENTITY.findall(text):
        if _mentions_other_employee(claimed, others):
            return True
    return False


def check_privacy(message: str, session: Session, catalog: Catalog) -> str | None:
    """Return the refusal text if the message is about another person, else None."""
    text = _normalize(message)
    me = catalog.employees[session.employee_id]
    others = _others(catalog, session)
    refused = (
        _mentions_other_employee(text, others)
        or _has_foreign_possessive(text, _allowed_possessives(catalog, me))
        or _GROUP_PHRASES.search(text) is not None
        or _claims_to_be_other(text, others)
    )
    return REFUSAL if refused else None
