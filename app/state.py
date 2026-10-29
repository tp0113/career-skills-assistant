"""The graph's state, and which fields are wiped at the start of every turn (PLAN 3.7)."""
from typing import Any, TypedDict

MAX_AGENT_STEPS = 6
MAX_REPAIRS = 2


class State(TypedDict, total=False):
    # Set by the server, never by the model.
    employee_id: str
    # This turn's input and result.
    user_message: str
    route: str
    route_source: str
    route_score: float
    reply: str
    outcome: str
    # Tool-use bookkeeping.
    llm_messages: list[dict]
    called_tools: list[str]
    agent_steps: int
    offered_tools: list[str]
    pending_calls: list[dict]
    profile: dict | None
    retrieved_courses: dict[str, dict]
    retrieved_jobs: dict[str, dict]
    flagged: list[dict]
    # Structured output and repair.
    compose_messages: list[dict]
    compose_raw: str
    repair_attempts: int
    verdict: str
    validation_errors: list[str]
    draft: dict | None
    # Output for the caller.
    events: list[dict]
    usage: dict[str, int]
    # Thread lifetime: survive between turns.
    recommendation: dict | None
    pending_course_id: str | None
    enrollment_confirmed: bool
    confirmed_course_id: str | None


def new_usage() -> dict[str, int]:
    return {"model_calls": 0, "prompt_tokens": 0, "output_tokens": 0, "latency_ms": 0, "compose_prompt_tokens": 0}


def fresh_turn() -> dict[str, Any]:
    """Turn fields back to empty. `recommendation` and the `pending_*` fields are left alone."""
    return {
        "route": "", "route_source": "", "route_score": 0.0, "reply": "", "outcome": "",
        "llm_messages": [], "called_tools": [], "agent_steps": 0, "offered_tools": [], "pending_calls": [],
        "profile": None, "retrieved_courses": {}, "retrieved_jobs": {}, "flagged": [],
        "compose_messages": [], "compose_raw": "", "repair_attempts": 0, "verdict": "",
        "validation_errors": [], "draft": None, "events": [], "usage": new_usage(),
    }
