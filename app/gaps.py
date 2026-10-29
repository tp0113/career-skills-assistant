"""Answer "which skills am I missing?" from the data. No model call.

The roles come from the employee's own career interest (the same keyword search the tools use), so
every line below can be traced to a data file. Postings the injection filter flags are skipped.
"""
from app.data import Catalog, Job
from app.injection import scan_text
from app.retrieval import search_jobs

MAX_ROLES = 2
MAX_COURSES = 3
NO_INTEREST_MATCH = (
    "I could not match your career interest to a role in our catalog, so I have no skill gaps to show. "
    "Try asking what skills you should develop."
)


def _is_clean(job: Job) -> bool:
    return not scan_text(job.title)[1] and not scan_text(job.description)[1]


def _roles_for_interest(catalog: Catalog, interest: str) -> list[Job]:
    rows = search_jobs(catalog, interest, limit=MAX_ROLES + 3)
    jobs = [catalog.jobs[row["id"]] for row in rows if _is_clean(catalog.jobs[row["id"]])]
    # A role that matches the interest much less than the best one is noise, so it is left out.
    best = next((row["score"] for row in rows if row["id"] == jobs[0].id), 0) if jobs else 0
    scores = {row["id"]: row["score"] for row in rows}
    return [job for job in jobs if scores[job.id] * 2 >= best][:MAX_ROLES]


def _courses_teaching(catalog: Catalog, skill_ids: list[str], completed: set[str]) -> list[str]:
    """Up to MAX_COURSES courses (not yet completed) that teach the most of the missing skills; ties by id."""
    wanted = set(skill_ids)
    covering = [(len(wanted & set(c.skills)), c) for c in catalog.courses.values() if c.id not in completed]
    covering = sorted((row for row in covering if row[0]), key=lambda row: (-row[0], row[1].id))
    return [f"{c.title} [{c.id}]" for _, c in covering[:MAX_COURSES]]


def render_gaps(employee_id: str, catalog: Catalog) -> str:
    me = catalog.employees[employee_id]
    roles = _roles_for_interest(catalog, me.career_interest)
    if not roles:
        return NO_INTEREST_MATCH
    lines = [f"Your career interest is: {me.career_interest}. Here is how the closest roles compare with your skills."]
    for job in roles:
        have = [s for s in job.required_skills if s in me.skills]
        missing = [s for s in job.required_skills if s not in me.skills]
        lines += ["", f"{job.title} [{job.id}]",
                  f"- You have: {', '.join(catalog.skill_names(have)) or 'none of the required skills yet'}",
                  f"- Missing: {', '.join(catalog.skill_names(missing)) or 'nothing, you have them all'}"]
        courses = _courses_teaching(catalog, missing, set(me.completed_courses))
        if missing and courses:
            lines.append(f"- Courses that teach them: {'; '.join(courses)}")
    lines += ["", "Ask me what skills you should develop for a full recommendation."]
    return "\n".join(lines)
