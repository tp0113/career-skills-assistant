"""Answer "list my skills" / "what are my courses" from the employee's own data. No model call.

Why in code: the facts are already in the data files, so a model would only add a chance to get
them wrong (the same idea as follow-ups). The id always comes from the signed-in session.
"""
import re

from app.data import Catalog

_COURSES = re.compile(r"\b(?:courses?|classes|class|training|completed|finished|taken|enrol\w*|registered|signed)\b", re.IGNORECASE)
_SKILLS = re.compile(r"\bskills?\b", re.IGNORECASE)


def _lines(title: str, items: list[str]) -> list[str]:
    return [title, *(f"- {item}" for item in items)] if items else [title, "- none yet"]


def render_profile(message: str, employee_id: str, catalog: Catalog, enrolled: list[str]) -> str:
    """The skills section, the courses section, or both, depending on what was asked."""
    me = catalog.employees[employee_id]
    wants_courses, wants_skills = bool(_COURSES.search(message)), bool(_SKILLS.search(message))
    lines = [f"Here is what I have on file for you, {me.name} ({me.current_role})."]
    if wants_skills or not wants_courses:
        lines += ["", *_lines("Your skills", catalog.skill_names(me.skills))]
    if wants_courses or not wants_skills:
        done = [f"{catalog.courses[c].title} [{c}]" for c in me.completed_courses]
        signed_up = [f"{catalog.courses[c].title} [{c}]" for c in enrolled if c in catalog.courses]
        lines += ["", *_lines("Courses you have completed", done), "", *_lines("Courses you are enrolled in", signed_up)]
    lines += ["", f"Career interest: {me.career_interest}"]
    return "\n".join(lines)
