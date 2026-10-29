"""Answer "list my skills" / "what are my courses" from the employee's own data. No model call.

Why in code: the facts are already in the data files, so a model would only add a chance to get
them wrong (the same idea as follow-ups). The id always comes from the signed-in session.
"""
import re

from app.data import Catalog
from app.injection import shown

_COURSES = re.compile(r"\b(?:courses?|classes|class|training|completed|finished|taken|enrol\w*|registered|signed)\b", re.IGNORECASE)
_SKILLS = re.compile(r"\bskills?\b", re.IGNORECASE)


def _lines(title: str, items: list[str]) -> list[str]:
    return [title, *(f"- {shown(item)}" for item in items)] if items else [title, "- none yet"]


def profile_card(employee_id: str, catalog: Catalog, enrolled: list[str]) -> dict:
    """The UI sidebar: the same facts as render_profile, as fields. Only this employee's own record."""
    me = catalog.employees[employee_id]
    course = lambda c: {"id": c, "title": shown(catalog.courses[c].title)}  # noqa: E731
    return {
        "id": me.id, "name": me.name, "current_role": me.current_role,
        "career_interest": shown(me.career_interest),
        "skills": [shown(name) for name in catalog.skill_names(me.skills)],
        "completed": [course(c) for c in me.completed_courses],
        "enrolled": [course(c) for c in enrolled if c in catalog.courses],
    }


def render_profile(message: str, employee_id: str, catalog: Catalog, enrolled: list[str]) -> str:
    """The skills section, the courses section, or both, depending on what was asked."""
    me = catalog.employees[employee_id]
    wants_courses, wants_skills = bool(_COURSES.search(message)), bool(_SKILLS.search(message))
    lines = [f"Here is what I have on file for you, {me.name} ({me.current_role})."]
    if wants_skills or not wants_courses:
        lines += ["", *_lines("Your skills", catalog.skill_names(me.skills))]
    if wants_courses or not wants_skills:
        done = [f"{shown(catalog.courses[c].title)} [{c}]" for c in me.completed_courses]
        signed_up = [f"{shown(catalog.courses[c].title)} [{c}]" for c in enrolled if c in catalog.courses]
        lines += ["", *_lines("Courses you have completed", done), "", *_lines("Courses you are enrolled in", signed_up)]
    lines += ["", f"Career interest: {shown(me.career_interest)}"]
    return "\n".join(lines)
