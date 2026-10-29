"""Turn a validated Recommendation into the message the user reads (F11).

Why in code: the only free text from the model on this path is each short reason, and it has
passed length and id checks. No model-written paragraph can ride along with an injected line.
"""
from app.schemas import Recommendation


def _sources(sources: list[str]) -> str:
    return f" (from {', '.join(sources)})"


def render_recommendation(rec: Recommendation) -> str:
    lines = ["Here is what I suggest for your next career step.", "", "Skills to develop"]
    lines += [f"{i}. {s.name}: {s.reason}{_sources(s.sources)}" for i, s in enumerate(rec.skills, start=1)]
    lines += ["", "Courses"]
    lines += [f"{i}. {c.title} [{c.course_id}]: {c.reason}{_sources(c.sources)}" for i, c in enumerate(rec.courses, start=1)]
    lines += ["", "Roles to explore"]
    lines += [f"{i}. {r.title} [{r.job_id}]: {r.reason}{_sources(r.sources)}" for i, r in enumerate(rec.roles, start=1)]
    lines += ["", "If you'd like to sign up for one of these courses, just ask, for example: \"Enroll me in the first course\"."]
    return "\n".join(lines)


def render_enroll_question(course_id: str, title: str) -> str:
    return f"Do you want me to enroll you in {title} [{course_id}]? Reply \"yes\" to confirm."


def render_enrolled(course_id: str, title: str, newly_added: bool) -> str:
    if newly_added:
        return f"Done. You are enrolled in {title} [{course_id}]."
    return f"You were already enrolled in {title} [{course_id}], so nothing changed."
