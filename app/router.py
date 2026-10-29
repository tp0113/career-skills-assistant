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

_ENROLL = re.compile(r"\b(?:enrol{1,2}|sign\s+me\s+up|register\s+me|sign\s+up\s+for)\b", re.IGNORECASE)
_ORDINAL = re.compile(r"\b(?:first|second|third|1st|2nd|3rd|last|that|tell\s+me\s+more|more\s+about)\b", re.IGNORECASE)
_ITEM_WORD = re.compile(r"\b(?:course|role|skill|one)s?\b", re.IGNORECASE)
_ADVISE = re.compile(
    r"\b(?:skills?|learn\w*|courses?|career|roles?|jobs?|grow\w*|develop\w*|next\s+step|promotion|improve\w*)\b",
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
    if rec is None:
        return False
    if _ORDINAL.search(message) and _ITEM_WORD.search(message):
        return True
    return bool(_title_words(rec) & set(tokenize(message)))


def route_message(message: str, recommendation: Recommendation | None = None) -> str:
    if _ENROLL.search(message):
        return ENROLL
    if _is_followup(message, recommendation):
        return FOLLOWUP
    if _ADVISE.search(message):
        return ADVISE
    return OUT_OF_SCOPE
