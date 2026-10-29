"""Check a recommendation in code. The last line of defence, so it works even if the model is fooled.

Each rule has its own error string. On failure the strings are sent back to the model so it can
repair its answer (the graph allows at most 2 repairs). With the injection defense off, only the
"flagged" checks are skipped; that is the "before" half of the before/after measurement.
"""
import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.data import Catalog
from app.schemas import (
    COURSE_RANGE, MAX_REASON_CHARS, ROLE_RANGE, SKILL_COUNT, CourseRec, ModelRecommendation,
    Recommendation, RoleRec, SkillRec,
)


@dataclass
class ValidationContext:
    """What this turn actually retrieved. Built by the graph from the tool context."""

    catalog: Catalog
    employee_id: str
    retrieved_courses: dict[str, dict]
    retrieved_jobs: dict[str, dict]
    flagged_ids: frozenset[str] = frozenset()
    defense: bool = True


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    recommendation: Recommendation | None = None


def candidate_skill_ids(catalog: Catalog, employee_id: str, courses: dict[str, dict], jobs: dict[str, dict]) -> list[str]:
    """Skills required by a retrieved job or taught by a retrieved course that the employee lacks."""
    held = set(catalog.employees[employee_id].skills)
    found: set[str] = set()
    for job_id in jobs:
        found.update(catalog.jobs[job_id].required_skills)
    for course_id in courses:
        found.update(catalog.courses[course_id].skills)
    return sorted(found - held)


def _count_error(label: str, count: int, low: int, high: int) -> str | None:
    if low <= count <= high:
        return None
    wanted = str(low) if low == high else f"{low} to {high}"
    return f"Give exactly {wanted} {label}, but there are {count}."


def _duplicates(label: str, ids: list[str]) -> list[str]:
    return [f"Duplicate {label} id {i}." for i in sorted({i for i in ids if ids.count(i) > 1})]


def _check_text(where: str, reason: str, sources: list[str], vctx: ValidationContext) -> list[str]:
    errors = []
    if not 1 <= len(reason.strip()) <= MAX_REASON_CHARS:
        errors.append(f"{where}: the reason must be 1 to {MAX_REASON_CHARS} characters.")
    if not sources:
        errors.append(f"{where}: give at least one source id.")
    for source in sources:
        errors.extend(_check_source(where, source, vctx))
    return errors


def _check_source(where: str, source: str, vctx: ValidationContext) -> list[str]:
    catalog = vctx.catalog
    if source not in catalog.courses and source not in catalog.jobs:
        return [f"{where}: source {source} does not exist."]
    if vctx.defense and source in vctx.flagged_ids:
        return [f"{where}: source {source} was flagged as unsafe and cannot be used."]
    if source not in vctx.retrieved_courses and source not in vctx.retrieved_jobs:
        return [f"{where}: source {source} was not retrieved in this conversation turn."]
    return []


def _check_skill(pick, vctx: ValidationContext, candidates: set[str]) -> list[str]:
    where = f"Skill {pick.skill_id}"
    if pick.skill_id not in vctx.catalog.skills:
        return [f"{where} does not exist."]
    errors = []
    if pick.skill_id in vctx.catalog.employees[vctx.employee_id].skills:
        errors.append(f"{where}: the employee already has this skill.")
    elif pick.skill_id not in candidates:
        errors.append(f"{where} is not one of the candidate skills.")
    return errors + _check_text(where, pick.reason, pick.sources, vctx)


def _check_course(pick, vctx: ValidationContext) -> list[str]:
    where = f"Course {pick.course_id}"
    if pick.course_id not in vctx.catalog.courses:
        return [f"{where} does not exist."]
    errors = []
    if pick.course_id in vctx.catalog.employees[vctx.employee_id].completed_courses:
        errors.append(f"{where}: the employee already completed this course.")
    elif vctx.defense and pick.course_id in vctx.flagged_ids:
        errors.append(f"{where} was flagged as unsafe and cannot be recommended.")
    elif pick.course_id not in vctx.retrieved_courses:
        errors.append(f"{where} was not retrieved in this conversation turn.")
    return errors + _check_text(where, pick.reason, pick.sources, vctx)


def _check_role(pick, vctx: ValidationContext) -> list[str]:
    where = f"Role {pick.job_id}"
    if pick.job_id not in vctx.catalog.jobs:
        return [f"{where} does not exist."]
    errors = []
    if vctx.defense and pick.job_id in vctx.flagged_ids:
        errors.append(f"{where} was flagged as unsafe and cannot be recommended.")
    elif pick.job_id not in vctx.retrieved_jobs:
        errors.append(f"{where} was not retrieved in this conversation turn.")
    return errors + _check_text(where, pick.reason, pick.sources, vctx)


def _parse(raw: str) -> tuple[ModelRecommendation | None, list[str]]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None, ["The answer is not valid JSON. Reply with only the JSON object."]
    try:
        return ModelRecommendation.model_validate(data), []
    except ValidationError as exc:
        return None, [f"Wrong shape at {'.'.join(str(p) for p in e['loc'])}: {e['msg']}." for e in exc.errors()]


def _rule_errors(model: ModelRecommendation, vctx: ValidationContext, candidates: set[str]) -> list[str]:
    errors = [e for e in (
        _count_error("skills", len(model.skills), SKILL_COUNT, SKILL_COUNT),
        _count_error("courses", len(model.courses), *COURSE_RANGE),
        _count_error("roles", len(model.roles), *ROLE_RANGE),
    ) if e]
    errors += _duplicates("skill", [p.skill_id for p in model.skills])
    errors += _duplicates("course", [p.course_id for p in model.courses])
    errors += _duplicates("job", [p.job_id for p in model.roles])
    for pick in model.skills:
        errors += _check_skill(pick, vctx, candidates)
    for pick in model.courses:
        errors += _check_course(pick, vctx)
    for pick in model.roles:
        errors += _check_role(pick, vctx)
    return errors


def _fill_names(model: ModelRecommendation, catalog: Catalog) -> Recommendation:
    """F12: names and titles come from the data, never from the model."""
    return Recommendation(
        skills=[SkillRec(**p.model_dump(), name=catalog.skills[p.skill_id].name) for p in model.skills],
        courses=[CourseRec(**p.model_dump(), title=catalog.courses[p.course_id].title) for p in model.courses],
        roles=[RoleRec(**p.model_dump(), title=catalog.jobs[p.job_id].title) for p in model.roles],
    )


def validate_recommendation(raw: str, vctx: ValidationContext) -> ValidationResult:
    model, errors = _parse(raw)
    if model is None:
        return ValidationResult(False, errors)
    candidates = set(candidate_skill_ids(vctx.catalog, vctx.employee_id, vctx.retrieved_courses, vctx.retrieved_jobs))
    errors = _rule_errors(model, vctx, candidates)
    if errors:
        return ValidationResult(False, errors)
    return ValidationResult(True, [], _fill_names(model, vctx.catalog))
