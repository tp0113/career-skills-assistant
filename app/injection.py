"""Find and remove lines that look like instructions inside retrieved text.

Why: retrieved text is data, but a poisoned record may try to give the model orders. This is layer 2
of the defense (layer 1 is labeling, layer 3 is output validation). It is a pattern filter, so it
catches known phrasings, not every possible attack. That limit is why layer 3 exists.
"""
import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("tells the model to ignore instructions",
     re.compile(r"\b(?:ignore|disregard|forget)\b.{0,40}\b(?:instructions?|prompts?|rules)\b", re.I)),
    ("tells the model to recommend to everyone",
     re.compile(r"\brecommend\b.{0,40}\bto\s+(?:everyone|everybody|all)\b", re.I)),
    ("tells the model what to say",
     re.compile(r"\bsay\s+(?:it|this|that)\s+is\s+the\s+best\b", re.I)),
    ("fake role tag", re.compile(r"^\s*(?:system|assistant|user)\s*:|\[/?inst\]|<\|", re.I)),
    ("gives the model orders", re.compile(r"\byou\s+(?:must|are\s+now|should\s+always)\b", re.I)),
]


def scan_text(text: str) -> tuple[str, list[str]]:
    """Return (text without suspicious lines, reasons for each removed line)."""
    kept = []
    flags = []
    for line in text.split("\n"):
        reasons = [reason for reason, pattern in _PATTERNS if pattern.search(line)]
        if reasons:
            flags.extend(reasons)
        else:
            kept.append(line)
    return "\n".join(kept).strip(), flags
