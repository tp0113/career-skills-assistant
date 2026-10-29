"""The four tools the model can call, and the one place that runs them.

Why this shape: no tool has an employee-id parameter. The id comes from the server-side Session,
so a fooled model cannot ask for someone else's data. Argument models forbid extra fields, so a
smuggled `employee_id` is rejected instead of ignored.
"""
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.data import Catalog
from app.session import Session


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=100)


class CourseArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: str = Field(pattern=r"^C\d{2}$")


# name -> (description shown to the model, argument model)
TOOLS: dict[str, tuple[str, type[BaseModel]]] = {
    "get_employee_profile": (
        "Get the signed-in employee's profile: role, skills, completed courses, career interest.",
        NoArgs,
    ),
    "search_courses": ("Search the course catalog by keywords. Returns the best 5 courses.", QueryArgs),
    "search_jobs": ("Search internal job postings by keywords. Returns the best 3 postings.", QueryArgs),
    "enroll_in_course": ("Propose enrolling the employee in a course by its id.", CourseArgs),
}


@dataclass
class ToolContext:
    """Per-turn state the tools read and fill. `offered=None` means every tool is allowed."""

    catalog: Catalog
    defense: bool = True
    offered: frozenset[str] | None = None
    retrieved_courses: dict[str, dict] = field(default_factory=dict)
    retrieved_jobs: dict[str, dict] = field(default_factory=dict)
    flagged: list[dict] = field(default_factory=list)


@dataclass
class ToolResult:
    ok: bool
    content_for_model: str
    data: dict[str, Any] | None = None
    error: str | None = None


def tool_schemas(names: list[str] | None = None) -> list[dict]:
    """JSON schemas in the shape Ollama's /api/chat expects, for the given tool names."""
    schemas = []
    for name in names if names is not None else list(TOOLS):
        description, model = TOOLS[name]
        parameters = model.model_json_schema()
        parameters.pop("title", None)
        for prop in parameters.get("properties", {}).values():
            prop.pop("title", None)
        schemas.append(
            {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}
        )
    return schemas


def _fail(message: str) -> ToolResult:
    return ToolResult(ok=False, content_for_model=f"Error: {message}", error=message)


def _wrap(source: str, data: dict) -> ToolResult:
    """Tool output goes to the model labeled as data, never as instructions."""
    body = json.dumps(data, ensure_ascii=False)
    return ToolResult(ok=True, content_for_model=f'<untrusted_data source="{source}">{body}</untrusted_data>', data=data)


def _parse_args(raw_args: dict | str | None) -> dict:
    if raw_args is None or raw_args == "":
        return {}
    parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    if not isinstance(parsed, dict):
        raise ValueError("arguments must be a JSON object")
    return parsed


def _profile(session: Session, ctx: ToolContext) -> ToolResult:
    emp = ctx.catalog.employees[session.employee_id]
    return _wrap("get_employee_profile", {
        "name": emp.name,
        "current_role": emp.current_role,
        "skills": [{"id": s, "name": ctx.catalog.skills[s].name} for s in emp.skills],
        "completed_courses": [{"id": c, "title": ctx.catalog.courses[c].title} for c in emp.completed_courses],
        "career_interest": emp.career_interest,
    })


def _propose_enrollment(args: CourseArgs) -> ToolResult:
    """Only a proposal. The write happens in the graph's enroll node, after a confirmation."""
    return ToolResult(
        ok=True,
        content_for_model=f"Enrollment in {args.course_id} proposed. Waiting for the employee to confirm.",
        data={"proposed_course_id": args.course_id},
    )


def _search_unavailable() -> ToolResult:
    return _fail("search is not available yet")


def execute_tool(name: str, raw_args: dict | str | None, session: Session, ctx: ToolContext) -> ToolResult:
    """Run one tool call from the model. Never raises: problems come back as `ok=False`."""
    if name not in TOOLS:
        return _fail(f"unknown tool '{name}'")
    if ctx.offered is not None and name not in ctx.offered:
        return _fail(f"tool '{name}' is not available right now")
    try:
        args = TOOLS[name][1].model_validate(_parse_args(raw_args))
    except (ValueError, ValidationError) as exc:
        return _fail(f"bad arguments for {name}: {exc}")
    if name == "get_employee_profile":
        return _profile(session, ctx)
    if name == "enroll_in_course":
        return _propose_enrollment(args)
    return _search_unavailable()
