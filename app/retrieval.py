"""Keyword search over courses and jobs, scored by a rule short enough to say out loud.

Score, per distinct query term: 3 if it is in the title, plus 2 if it is in one of the skill
names, plus 1 if it is in the description. Ties are broken by id, so results are repeatable.
Every result keeps its id, score and matched terms: those are the provenance shown to the user.
Why not vectors: this is explainable in 30 seconds and the catalog is tiny.
"""
import re

from app.data import Catalog, Course, Job

STOPWORDS = frozenset(
    "a an and are as at be but by can for from has have how i in into is it me my of on or "
    "should that the to what which with would you your".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-letters, drop stopwords. Order is kept, repeats are removed."""
    seen: dict[str, None] = {}
    for word in re.findall(r"[a-z]+", text.lower()):
        if word not in STOPWORDS:
            seen.setdefault(word, None)
    return list(seen)


def score(terms: list[str], title: str, skill_names: list[str], description: str) -> tuple[int, list[str]]:
    """Return (score, matched terms in query order)."""
    in_title = set(tokenize(title))
    in_skills = set(tokenize(" ".join(skill_names)))
    in_description = set(tokenize(description))
    total = 0
    matched = []
    for term in terms:
        points = 3 * (term in in_title) + 2 * (term in in_skills) + (term in in_description)
        if points:
            total += points
            matched.append(term)
    return total, matched


def _rank(scored: list[tuple[int, str, dict]], limit: int) -> list[dict]:
    """Best score first, then id. Items with score 0 never appear."""
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[:limit]]


def _course_row(course: Course, catalog: Catalog, points: int, matched: list[str]) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "level": course.level,
        "duration_hours": course.duration_hours,
        "skills": catalog.skill_names(course.skills),
        "description": course.description,
        "score": points,
        "matched_terms": matched,
    }


def _job_row(job: Job, catalog: Catalog, points: int, matched: list[str]) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "required_skills": catalog.skill_names(job.required_skills),
        "description": job.description,
        "score": points,
        "matched_terms": matched,
    }


def search_courses(catalog: Catalog, query: str, exclude_ids: frozenset[str] | set[str] = frozenset(),
                   limit: int = 5) -> list[dict]:
    terms = tokenize(query)
    scored = []
    for course in catalog.courses.values():
        if course.id in exclude_ids:
            continue
        points, matched = score(terms, course.title, catalog.skill_names(course.skills), course.description)
        if points:
            scored.append((points, course.id, _course_row(course, catalog, points, matched)))
    return _rank(scored, limit)


def search_jobs(catalog: Catalog, query: str, limit: int = 3) -> list[dict]:
    terms = tokenize(query)
    scored = []
    for job in catalog.jobs.values():
        points, matched = score(terms, job.title, catalog.skill_names(job.required_skills), job.description)
        if points:
            scored.append((points, job.id, _job_row(job, catalog, points, matched)))
    return _rank(scored, limit)
