"""Load the synthetic JSON files into typed records and check they agree with each other.

Why: every later module (guard, tools, validation) trusts that ids point at real records.
Checking once at load time, and failing loudly, is cheaper than checking everywhere.
"""
import json
from pathlib import Path

from pydantic import BaseModel


class DataError(Exception):
    """The data files are missing, malformed or contradict each other."""


class Skill(BaseModel):
    id: str
    name: str
    category: str
    description: str
    roles: list[str]


class Course(BaseModel):
    id: str
    title: str
    description: str
    skills: list[str]
    level: str
    duration_hours: int


class Job(BaseModel):
    id: str
    title: str
    description: str
    required_skills: list[str]


class Employee(BaseModel):
    id: str
    name: str
    current_role: str
    skills: list[str]
    completed_courses: list[str]
    career_interest: str


class Catalog(BaseModel):
    """Everything in data/, keyed by id. Read-only at runtime."""

    employees: dict[str, Employee]
    skills: dict[str, Skill]
    courses: dict[str, Course]
    jobs: dict[str, Job]

    def skill_names(self, skill_ids: list[str]) -> list[str]:
        return [self.skills[s].name for s in skill_ids]


def _read_items(path: Path) -> list[dict]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise DataError(f"{path.name} must be an object with an 'items' list")
    return raw["items"]


def _by_id(model: type[BaseModel], path: Path) -> dict:
    records = {}
    for item in _read_items(path):
        record = model.model_validate(item)
        if record.id in records:
            raise DataError(f"{path.name}: duplicate id {record.id}")
        records[record.id] = record
    return records


def _check_refs(catalog: Catalog) -> None:
    """Every skill and course id mentioned anywhere must exist."""
    for emp in catalog.employees.values():
        _need(emp.skills, catalog.skills, f"employee {emp.id} skill")
        _need(emp.completed_courses, catalog.courses, f"employee {emp.id} course")
    for course in catalog.courses.values():
        _need(course.skills, catalog.skills, f"course {course.id} skill")
    for job in catalog.jobs.values():
        _need(job.required_skills, catalog.skills, f"job {job.id} skill")


def _need(ids: list[str], known: dict, where: str) -> None:
    for item_id in ids:
        if item_id not in known:
            raise DataError(f"{where}: unknown id {item_id}")


def load_catalog(data_dir: Path) -> Catalog:
    catalog = Catalog(
        employees=_by_id(Employee, data_dir / "employees.json"),
        skills=_by_id(Skill, data_dir / "skills.json"),
        courses=_by_id(Course, data_dir / "courses.json"),
        jobs=_by_id(Job, data_dir / "jobs.json"),
    )
    _check_refs(catalog)
    return catalog
