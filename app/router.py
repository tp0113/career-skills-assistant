"""Deterministic routing (F7): keyword rules, checked in a fixed order.

Why rules and not the model: a small model is unreliable at routing, and rules can be tested
and explained. The privacy guard has already run before this.
"""
import re

from app.retrieval import tokenize
from app.schemas import Recommendation

ENROLL = "enroll"
FOLLOWUP = "followup"
ADVISE = "advise"
OUT_OF_SCOPE = "out_of_scope"
PROFILE = "profile"

_ENROLL = re.compile(r"\b(?:enrol{1,2}|sign\s+me\s+up|register\s+me|sign\s+up\s+for)\b", re.IGNORECASE)
# "the second course", "that one", "the last machine learning course": a position, then the item word
# within two words. "the last day of my course" is too far apart, so it is not a follow-up.
_POSITION = re.compile(
    r"\b(?:first|second|third|1st|2nd|3rd|last|that|this)\s+(?:\w+\s+){0,2}?(?:course|role|job|skill|one)s?\b",
    re.IGNORECASE,
)
_MORE = re.compile(r"\b(?:tell\s+me\s+more|more\s+about)\b", re.IGNORECASE)
_ITEM_WORD = re.compile(r"\b(?:course|role|job|skill|one)s?\b", re.IGNORECASE)
# A title word only counts when the message asks about something already shown.
_ASKS_ABOUT = re.compile(
    r"\b(?:tell\s+me\s+(?:more\s+)?about|more\s+about|what\s+about|explain|describe|details?|"
    r"what\s+is|what's|how\s+long)\b",
    re.IGNORECASE,
)
# Asking for something new is a fresh request, even if it repeats a saved title word.
_FRESH = re.compile(r"\b(?:recommend\w*|suggest\w*|different|other|another|new|instead|alternatives?)\b", re.IGNORECASE)
_ADVISE = re.compile(
    r"\b(?:skills?|learn\w*|courses?|career|roles?|jobs?|grow\w*|develop\w*|next\s+step|promotion|improve\w*)\b",
    re.IGNORECASE,
)
# "list my skills", "what are my courses", "what have I completed": a plain question about own data.
_LIST_START = re.compile(r"^\W*(?:please\s+)?(?:list|show|display|what(?:'s|\s+are|\s+is)?|which|tell\s+me|give\s+me)\b", re.IGNORECASE)
# The own-data phrase must end the message ("... my course?"), so "the weather on the last day of my course" is not one.
_OWN_DATA = re.compile(
    r"(?:\bmy\s+(?:current\s+|completed\s+)?(?:skills?|courses?|training|profile)(?:\s+and\s+(?:my\s+)?(?:skills?|courses?))?"
    r"|\b(?:skills?|courses?)\s+(?:do\s+|have\s+)?i\s+(?:have|know|completed|finished|taken)"
    r"|\bwhat\s+have\s+i\s+(?:completed|taken|finished))"
    r"(?:\s+(?:so\s+far|currently|now|please))*\W*$",
    re.IGNORECASE,
)
# The list word must come straight before the own-data phrase: "what is the weather on the last day of my course" fails.
_PROFILE_FORM = re.compile(_LIST_START.pattern + r"\s+(?:the\s+|all\s+)?" + _OWN_DATA.pattern, re.IGNORECASE)
# Any of these means the person wants advice, so "what courses fit my skills" is not a profile question.
_WANTS_ADVICE = re.compile(
    r"\b(?:recommend\w*|suggest\w*|should|next|improve\w*|develop\w*|learn\w*|grow\w*|career|promotion|"
    r"missing|lack\w*|need\w*|fit|best|new|role|job)s?\b",
    re.IGNORECASE,
)
# Title words too common to identify one recommended item.
_GENERIC_TITLE_WORDS = {"basics", "essentials", "introduction", "foundations", "applications", "engineer", "manager", "technical"}


def _title_words(rec: Recommendation) -> set[str]:
    words: set[str] = set()
    for title in [c.title for c in rec.courses] + [r.title for r in rec.roles]:
        words.update(w for w in tokenize(title) if len(w) >= 4 and w not in _GENERIC_TITLE_WORDS)
    return words


def _is_followup(message: str, rec: Recommendation | None) -> bool:
    """Codex checkpoint 2: a saved title word alone used to make any message a follow-up."""
    if rec is None or _FRESH.search(message):
        return False
    if _POSITION.search(message) or (_MORE.search(message) and _ITEM_WORD.search(message)):
        return True
    return bool(_ASKS_ABOUT.search(message) and _title_words(rec) & set(tokenize(message)))


def _is_profile_question(message: str) -> bool:
    return bool(_PROFILE_FORM.match(message) and not _WANTS_ADVICE.search(message))


def _first_person(message: str, own_names: tuple[str, ...]) -> str:
    """"What are Marcus's skills?" from Marcus himself is a question about "my" skills (the guard let it through)."""
    for name in own_names:
        message = re.sub(rf"\b{re.escape(name)}(?:'s|’s)", "my", message, flags=re.IGNORECASE)
    return message


def route_message(message: str, recommendation: Recommendation | None = None, own_names: tuple[str, ...] = ()) -> str:
    if _ENROLL.search(message):
        return ENROLL
    if _is_profile_question(_first_person(message, own_names)):
        return PROFILE
    if _is_followup(message, recommendation):
        return FOLLOWUP
    if _ADVISE.search(message):
        return ADVISE
    return OUT_OF_SCOPE
