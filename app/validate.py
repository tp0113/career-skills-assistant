"""Check a recommendation in code. The last line of defence, so it works even if the model is fooled.

Each rule has its own error string. On failure the strings are sent back to the model so it can
repair its answer (the graph allows at most 2 repairs). With the injection defense off, only the
"flagged" and "reads like an instruction" checks are skipped; that is the "before" half of the
before/after measurement.
"""
import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.data import Catalog
from app.guard import mentions_another_employee
from app.injection import scan_text
from app.session import Session
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


_ID = re.compile(r"\b[CJS]\d{2}\b", re.IGNORECASE)


def _supports(kind: str, item_id: str, source: str, catalog: Catalog) -> bool:
    """A source supports a pick if it is the item itself, or shares a skill with it in the data.

    skill: the course teaches it or the job needs it. course: a job needs a skill the course
    teaches. role: a course teaches a skill the job needs.
    """
    if source == item_id:
        return kind != "skill"
    taught = set(catalog.courses[source].skills) if source in catalog.courses else set()
    needed = set(catalog.jobs[source].required_skills) if source in catalog.jobs else set()
    if kind == "skill":
        return item_id in taught | needed
    if kind == "course":
        return bool(needed & set(catalog.courses[item_id].skills))
    return bool(taught & set(catalog.jobs[item_id].required_skills))


def _check_reason(where: str, reason: str, vctx: ValidationContext, allowed_ids: set[str]) -> list[str]:
    """The reason is the one free text the user sees, so it is checked for what it says, not only its length."""
    errors = []
    if not 1 <= len(reason.strip()) <= MAX_REASON_CHARS:
        errors.append(f"{where}: the reason must be 1 to {MAX_REASON_CHARS} characters.")
    if "\n" in reason or "\r" in reason:
        errors.append(f"{where}: the reason must be one line.")
    for mentioned in sorted({m.upper() for m in _ID.findall(reason)} - allowed_ids):
        errors.append(f"{where}: the reason mentions {mentioned}, which is not part of this recommendation.")
    if mentions_another_employee(reason, Session(vctx.employee_id), vctx.catalog):
        errors.append(f"{where}: the reason mentions another employee.")
    if vctx.defense and any(_flagged_title(i, vctx).lower() in reason.lower() for i in vctx.flagged_ids):
        errors.append(f"{where}: the reason mentions a posting that was flagged as unsafe.")
    if vctx.defense and scan_text(reason)[1]:
        errors.append(f"{where}: the reason reads like an instruction. Say only why it fits the employee.")
    return errors


def _flagged_title(item_id: str, vctx: ValidationContext) -> str:
    item = vctx.catalog.jobs.get(item_id) or vctx.catalog.courses.get(item_id)
    return item.title if item else item_id


def _check_text(where: str, kind: str, item_id: str, pick, vctx: ValidationContext, allowed_ids: set[str]) -> list[str]:
    errors = _check_reason(where, pick.reason, vctx, allowed_ids)
    if not pick.sources:
        return errors + [f"{where}: give at least one source id."]
    source_errors = [e for source in pick.sources for e in _check_source(where, source, vctx)]
    if not source_errors and not any(_supports(kind, item_id, s, vctx.catalog) for s in pick.sources):
        source_errors.append(f"{where}: none of its sources support it. Cite a course or job that shares a skill with it.")
    return errors + source_errors


def _check_source(where: str, source: str, vctx: ValidationContext) -> list[str]:
    catalog = vctx.catalog
    if source not in catalog.courses and source not in catalog.jobs:
        return [f"{where}: source {source} does not exist."]
    if vctx.defense and source in vctx.flagged_ids:
        return [f"{where}: source {source} was flagged as unsafe and cannot be used."]
    if source not in vctx.retrieved_courses and source not in vctx.retrieved_jobs:
        return [f"{where}: source {source} was not retrieved in this conversation turn."]
    return []


def _check_skill(pick, vctx: ValidationContext, candidates: set[str], allowed_ids: set[str]) -> list[str]:
    where = f"Skill {pick.skill_id}"
    if pick.skill_id not in vctx.catalog.skills:
        return [f"{where} does not exist."]
    errors = []
    if pick.skill_id in vctx.catalog.employees[vctx.employee_id].skills:
        errors.append(f"{where}: the employee already has this skill.")
    elif pick.skill_id not in candidates:
        errors.append(f"{where} is not one of the candidate skills.")
    return errors + _check_text(where, "skill", pick.skill_id, pick, vctx, allowed_ids)


def _check_course(pick, vctx: ValidationContext, allowed_ids: set[str]) -> list[str]:
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
    return errors + _check_text(where, "course", pick.course_id, pick, vctx, allowed_ids)


def _check_role(pick, vctx: ValidationContext, allowed_ids: set[str]) -> list[str]:
    where = f"Role {pick.job_id}"
    if pick.job_id not in vctx.catalog.jobs:
        return [f"{where} does not exist."]
    errors = []
    if vctx.defense and pick.job_id in vctx.flagged_ids:
        errors.append(f"{where} was flagged as unsafe and cannot be recommended.")
    elif pick.job_id not in vctx.retrieved_jobs:
        errors.append(f"{where} was not retrieved in this conversation turn.")
    return errors + _check_text(where, "role", pick.job_id, pick, vctx, allowed_ids)


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
    allowed_ids = _ids_in(model)
    for pick in model.skills:
        errors += _check_skill(pick, vctx, candidates, allowed_ids)
    for pick in model.courses:
        errors += _check_course(pick, vctx, allowed_ids)
    for pick in model.roles:
        errors += _check_role(pick, vctx, allowed_ids)
    return errors


def _ids_in(model: ModelRecommendation) -> set[str]:
    """Every id in the recommendation: a reason may mention these and nothing else."""
    picks = [(p.skill_id, p.sources) for p in model.skills] + [(p.course_id, p.sources) for p in model.courses] \
        + [(p.job_id, p.sources) for p in model.roles]
    return {i.upper() for item_id, sources in picks for i in [item_id, *sources]}


def _fill_names(model: ModelRecommendation, catalog: Catalog) -> Recommendation:
    """F12: names and titles come from the data, never from the model. Sources that do not support a pick are dropped."""
    def kept(kind: str, item_id: str, sources: list[str]) -> list[str]:
        return [s for s in sources if _supports(kind, item_id, s, catalog)]

    return Recommendation(
        skills=[SkillRec(skill_id=p.skill_id, reason=p.reason, sources=kept("skill", p.skill_id, p.sources),
                         name=catalog.skills[p.skill_id].name) for p in model.skills],
        courses=[CourseRec(course_id=p.course_id, reason=p.reason, sources=kept("course", p.course_id, p.sources),
                           title=catalog.courses[p.course_id].title) for p in model.courses],
        roles=[RoleRec(job_id=p.job_id, reason=p.reason, sources=kept("role", p.job_id, p.sources),
                       title=catalog.jobs[p.job_id].title) for p in model.roles],
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
