"""Follow-up questions ("tell me more about the second course"), answered in code with no model call.

Why no model: the saved recommendation already holds the ids. Code resolves which item the
employee means and renders the answer from the data files, so there is no free prose for an
injected line to ride along with (same idea as rule 4/5 and F11).
"""
import re

from app.data import Catalog
from app.injection import scan_text
from app.retrieval import tokenize
from app.schemas import Recommendation

ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": -1}
CLARIFY = ("I wasn't sure which item you mean. Say for example \"tell me more about the second course\" "
           "or name a recommended course or role.")
_KIND = re.compile(r"\b(course|role|skill)s?\b", re.IGNORECASE)


def _kind_of(message: str) -> str:
    """'role' or 'skill' if the message says so; anything else (including "one") means a course."""
    found = _KIND.search(message)
    return found.group(1).lower() if found else "course"


def _items(rec: Recommendation, kind: str) -> list[tuple[str, str]]:
    """(id, title) of the recommended items of this kind, in the order shown."""
    if kind == "role":
        return [(r.job_id, r.title) for r in rec.roles]
    if kind == "skill":
        return [(s.skill_id, s.name) for s in rec.skills]
    return [(c.course_id, c.title) for c in rec.courses]


def resolve(message: str, rec: Recommendation) -> tuple[str, str] | None:
    """Which recommended item the message means, as (kind, id); None if it is unclear.

    A title word wins over an ordinal ("tell me more about Docker"); an ordinal needs a position
    that exists in that list.
    """
    words = set(tokenize(message))
    for kind in ("course", "role", "skill"):
        hits = [(i, t) for i, t in _items(rec, kind) if {w for w in tokenize(t) if len(w) >= 4} & words]
        if len(hits) == 1:
            return kind, hits[0][0]
    kind = _kind_of(message)
    items = _items(rec, kind)
    for word, position in ORDINALS.items():
        if re.search(rf"\b{word}\b", message, re.IGNORECASE):
            try:
                return kind, items[position][0]
            except IndexError:
                return None
    return None


def _names(catalog: Catalog, skill_ids: list[str]) -> str:
    return ", ".join(catalog.skill_names(skill_ids)) or "none listed"


def _course_text(catalog: Catalog, rec: Recommendation, course_id: str) -> str:
    course = catalog.courses[course_id]
    pick = next(c for c in rec.courses if c.course_id == course_id)
    return "\n".join([
        f"{course.title} [{course_id}]",
        f"Level: {course.level}. Length: {course.duration_hours} hours.",
        f"Teaches: {_names(catalog, course.skills)}.",
        f"About: {scan_text(course.description)[0]}",
        f"Why I suggested it: {pick.reason}",
        f"To sign up, say \"Enroll me in {course.title}\".",
    ])


def _role_text(catalog: Catalog, employee_id: str, rec: Recommendation, job_id: str) -> str:
    job = catalog.jobs[job_id]
    pick = next(r for r in rec.roles if r.job_id == job_id)
    held = set(catalog.employees[employee_id].skills)
    have = [s for s in job.required_skills if s in held]
    lack = [s for s in job.required_skills if s not in held]
    return "\n".join([
        f"{job.title} [{job_id}]",
        f"Needs: {_names(catalog, job.required_skills)}.",
        f"You already have: {_names(catalog, have)}. You still need: {_names(catalog, lack)}.",
        f"About: {scan_text(job.description)[0]}",
        f"Why I suggested it: {pick.reason}",
    ])


def _skill_text(catalog: Catalog, rec: Recommendation, skill_id: str) -> str:
    skill = catalog.skills[skill_id]
    pick = next(s for s in rec.skills if s.skill_id == skill_id)
    teaching = [f"{c.title} [{c.course_id}]" for c in rec.courses if skill_id in catalog.courses[c.course_id].skills]
    lines = [f"{skill.name} [{skill_id}]", f"Category: {skill.category}.", f"About: {scan_text(skill.description)[0]}"]
    if teaching:
        lines.append(f"Recommended courses that teach it: {', '.join(teaching)}.")
    lines.append(f"Why I suggested it: {pick.reason}")
    return "\n".join(lines)


def render_followup(message: str, rec: Recommendation, catalog: Catalog, employee_id: str) -> str:
    """The reply for a follow-up. Unclear references get a short question, never a guess."""
    target = resolve(message, rec)
    if target is None:
        return CLARIFY
    kind, item_id = target
    if kind == "role":
        return _role_text(catalog, employee_id, rec, item_id)
    if kind == "skill":
        return _skill_text(catalog, rec, item_id)
    return _course_text(catalog, rec, item_id)
