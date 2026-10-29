"""Every node of the graph. Each takes the state and returns only the fields it changes.

The dependencies (catalog, model, enrollment store) are held by `Nodes`, not by the state,
because the state is saved by the checkpointer and must stay plain data.
"""
from app import prompts
from app.confirmation import answer_is_yes
from app.data import Catalog
from app.enrollments import EnrollmentStore
from app.guard import check_privacy
from app.llm import LLM, LLMError, LLMReply
from app.render import render_enroll_question, render_enrolled, render_recommendation
from app.router import ADVISE, ENROLL, FOLLOWUP, OUT_OF_SCOPE, route_message
from app.schemas import Recommendation, recommendation_json_schema
from app.session import Session
from app.state import MAX_AGENT_STEPS, MAX_REPAIRS, State, fresh_turn
from app.tools import ToolContext, execute_tool, tool_schemas
from app.validate import ValidationContext, candidate_skill_ids, validate_recommendation
from langgraph.types import interrupt

PROFILE = "get_employee_profile"
SEARCHES = ("search_courses", "search_jobs")
MODEL_ERROR = "model_error"
# The answer needs 2 to 3 courses and 1 to 2 roles, so a search is only "done" once this many were retrieved.
MIN_RESULTS = {"search_courses": 2, "search_jobs": 1}


def offered_tools(called: list[str]) -> list[str]:
    """Staged offering (F8): the profile first, then both searches until both have been called."""
    if PROFILE not in called:
        return [PROFILE]
    return list(SEARCHES)


def _enough(search: str, ctx: ToolContext) -> bool:
    """Counts items retrieved so far this turn, across all searches of that kind."""
    store = ctx.retrieved_courses if search == "search_courses" else ctx.retrieved_jobs
    return len(store) >= MIN_RESULTS[search]


def required_calls_done(called: list[str]) -> bool:
    return PROFILE in called and all(name in called for name in SEARCHES)


def _add_usage(usage: dict, reply: LLMReply) -> dict:
    return {
        **usage,
        "model_calls": usage["model_calls"] + 1,
        "prompt_tokens": usage["prompt_tokens"] + reply.prompt_tokens,
        "output_tokens": usage["output_tokens"] + reply.output_tokens,
        "latency_ms": usage["latency_ms"] + reply.latency_ms,
    }


def _shown_arguments(call: dict, ok: bool):
    """Events go to the CLI and later the UI. A rejected call shows only its argument names, not the values."""
    if ok:
        return call["arguments"]
    args = call["arguments"]
    return sorted(args) if isinstance(args, dict) else "<not a JSON object>"


def _assistant_message(reply: LLMReply) -> dict:
    """The assistant turn as Ollama wants to see it again: arguments as an object."""
    calls = [
        {"function": {"name": c["name"], "arguments": c["arguments"] if isinstance(c["arguments"], dict) else {}}}
        for c in reply.tool_calls
    ]
    return {"role": "assistant", "content": reply.content, "tool_calls": calls}


class Nodes:
    def __init__(self, catalog: Catalog, llm: LLM, store: EnrollmentStore, defense: bool) -> None:
        self.catalog = catalog
        self.llm = llm
        self.store = store
        self.defense = defense

    # ---- entry: guard, route, canned answers -------------------------------------------------

    def guard(self, state: State) -> dict:
        """First node of every turn: wipe turn fields, then refuse before any model call (F6)."""
        update = fresh_turn()
        refusal = check_privacy(state["user_message"], Session(state["employee_id"]), self.catalog)
        if refusal:
            return {**update, "route": "refuse", "reply": refusal, "outcome": "refused"}
        return update

    def route(self, state: State) -> dict:
        rec = state.get("recommendation")
        return {"route": route_message(state["user_message"], Recommendation.model_validate(rec) if rec else None)}

    def out_of_scope(self, state: State) -> dict:
        return {"reply": prompts.OUT_OF_SCOPE, "outcome": "out_of_scope"}

    def tool_fallback(self, state: State) -> dict:
        return {"reply": prompts.TOOL_FALLBACK, "outcome": "tool_fallback"}

    # ---- advise path -------------------------------------------------------------------------

    def advise_agent(self, state: State) -> dict:
        """One model step: it chooses the tool call and its arguments; the graph chose what was offered."""
        offered = offered_tools(state["called_tools"])
        messages = [
            {"role": "system", "content": prompts.ADVISE_SYSTEM},
            {"role": "user", "content": state["user_message"]},
            *state["llm_messages"],
        ]
        try:
            reply = self.llm.chat(messages, tools=tool_schemas(offered))
        except LLMError:
            return {"reply": prompts.MODEL_UNAVAILABLE, "outcome": MODEL_ERROR}
        update = {"usage": _add_usage(state["usage"], reply), "agent_steps": state["agent_steps"] + 1}
        if reply.tool_calls:
            return {**update, "offered_tools": offered, "pending_calls": reply.tool_calls,
                    "llm_messages": [*state["llm_messages"], _assistant_message(reply)]}
        # F9: prose instead of a tool call. One short reminder, then ask again.
        reminder = [{"role": "assistant", "content": reply.content}, {"role": "user", "content": prompts.TOOL_REMINDER}]
        return {**update, "pending_calls": [], "llm_messages": [*state["llm_messages"], *reminder]}

    def run_tools(self, state: State) -> dict:
        """Run what the model asked for. The signed-in id comes from the state, never from the call."""
        session = Session(state["employee_id"])
        ctx = ToolContext(
            catalog=self.catalog, defense=self.defense, offered=frozenset(state["offered_tools"]),
            retrieved_courses=dict(state["retrieved_courses"]), retrieved_jobs=dict(state["retrieved_jobs"]),
            flagged=list(state["flagged"]),
        )
        messages, events = list(state["llm_messages"]), list(state["events"])
        called, profile = list(state["called_tools"]), state["profile"]
        for call in state["pending_calls"]:
            result = execute_tool(call["name"], call["arguments"], session, ctx)
            too_few = result.ok and call["name"] in SEARCHES and not _enough(call["name"], ctx)
            messages.append({"role": "tool", "tool_name": call["name"], "content": result.content_for_model})
            if too_few:
                hint = prompts.too_few_hint(self._missing_skill_names(state["employee_id"]))
                messages.append({"role": "user", "content": hint})
            events.append({"type": "tool", "name": call["name"], "arguments": _shown_arguments(call, result.ok),
                           "ok": result.ok, "error": result.error, "too_few": too_few})
            # A search that leaves too few items does not count: the model must try again with other words.
            if result.ok and not too_few and call["name"] not in called:
                called.append(call["name"])
            if result.ok and call["name"] == PROFILE:
                profile = result.data
        return {"llm_messages": messages, "events": events, "called_tools": called, "profile": profile,
                "pending_calls": [], "retrieved_courses": ctx.retrieved_courses,
                "retrieved_jobs": ctx.retrieved_jobs, "flagged": ctx.flagged}

    def _missing_skill_names(self, employee_id: str) -> list[str]:
        """Catalog skills the employee lacks, in id order: words the keyword search is sure to know."""
        held = set(self.catalog.employees[employee_id].skills)
        return [skill.name for sid, skill in sorted(self.catalog.skills.items()) if sid not in held]

    def compose(self, state: State) -> dict:
        """The one structured-output call (F10). On a repair the messages already hold the errors."""
        messages = state["compose_messages"] or self._first_compose_messages(state)
        try:
            reply = self.llm.chat(messages, json_schema=recommendation_json_schema())
        except LLMError:
            return {"reply": prompts.MODEL_UNAVAILABLE, "outcome": MODEL_ERROR}
        usage = _add_usage(state["usage"], reply)
        if not state["compose_messages"]:
            usage["compose_prompt_tokens"] = reply.prompt_tokens
        return {"usage": usage, "compose_messages": messages, "compose_raw": reply.content}

    def _first_compose_messages(self, state: State) -> list[dict]:
        courses, jobs = state["retrieved_courses"], state["retrieved_jobs"]
        candidates = [
            {"id": sid, "name": self.catalog.skills[sid].name}
            for sid in candidate_skill_ids(self.catalog, state["employee_id"], courses, jobs)
        ]
        return prompts.compose_messages(
            state["user_message"], state["profile"], list(courses.values()), list(jobs.values()), candidates
        )

    def validate(self, state: State) -> dict:
        vctx = ValidationContext(
            catalog=self.catalog, employee_id=state["employee_id"],
            retrieved_courses=state["retrieved_courses"], retrieved_jobs=state["retrieved_jobs"],
            flagged_ids=frozenset(f["id"] for f in state["flagged"]), defense=self.defense,
        )
        result = validate_recommendation(state["compose_raw"], vctx)
        if result.ok:
            return {"verdict": "ok", "draft": result.recommendation.model_dump(), "validation_errors": []}
        if state["repair_attempts"] < MAX_REPAIRS:
            history = [{"role": "assistant", "content": state["compose_raw"]}, prompts.repair_message(result.errors)]
            return {"verdict": "repair", "validation_errors": result.errors,
                    "repair_attempts": state["repair_attempts"] + 1,
                    "compose_messages": [*state["compose_messages"], *history]}
        return {"verdict": "failed", "validation_errors": result.errors,
                "reply": prompts.VALIDATION_FAILURE, "outcome": "validation_failed"}

    def respond(self, state: State) -> dict:
        """F11: the message is rendered in code from the validated object. A new recommendation clears any old enrollment."""
        rec = Recommendation.model_validate(state["draft"])
        return {"reply": render_recommendation(rec), "recommendation": state["draft"], "outcome": "ok",
                "pending_course_id": None, "enrollment_confirmed": False, "confirmed_course_id": None}

    # ---- enroll path -------------------------------------------------------------------------

    def enroll_agent(self, state: State) -> dict:
        """The model may only propose a course id. Code decides whether the proposal is allowed."""
        rec = state.get("recommendation")
        if not rec:
            return {"reply": prompts.NO_RECOMMENDATION, "outcome": "enroll_clarify"}
        try:
            reply = self.llm.chat(prompts.enroll_messages(state["user_message"], rec["courses"]),
                                  tools=tool_schemas(["enroll_in_course"]))
        except LLMError:
            return {"reply": prompts.MODEL_UNAVAILABLE, "outcome": MODEL_ERROR}
        update = {"usage": _add_usage(state["usage"], reply), "pending_course_id": None,
                  "enrollment_confirmed": False, "confirmed_course_id": None}
        if not reply.tool_calls:
            return {**update, "reply": prompts.ENROLL_CLARIFY, "outcome": "enroll_clarify"}
        call = reply.tool_calls[0]
        ctx = ToolContext(catalog=self.catalog, defense=self.defense, offered=frozenset({"enroll_in_course"}))
        result = execute_tool(call["name"], call["arguments"], Session(state["employee_id"]), ctx)
        event = {"type": "tool", "name": call["name"], "arguments": _shown_arguments(call, result.ok),
                 "ok": result.ok, "error": result.error}
        if not result.ok:
            return {**update, "events": [event], "reply": prompts.ENROLL_CLARIFY, "outcome": "enroll_clarify"}
        course_id = result.data["proposed_course_id"]
        problem = self._enroll_problem(state["employee_id"], course_id)
        if problem:
            return {**update, "events": [event], "reply": problem, "outcome": "enroll_refused"}
        return {**update, "events": [event], "pending_course_id": course_id, "outcome": "enroll_proposed"}

    def _enroll_problem(self, employee_id: str, course_id: str) -> str | None:
        """Code checks (PLAN 3.6): the course exists, is not completed, and is not already booked."""
        course = self.catalog.courses.get(course_id)
        if course is None:
            return prompts.ENROLL_CLARIFY
        if course_id in self.catalog.employees[employee_id].completed_courses:
            return f"You have already completed {course.title} [{course_id}], so there is no need to enroll."
        if course_id in self.store.list_for(employee_id):
            return f"You are already enrolled in {course.title} [{course_id}]."
        return None

    def confirm(self, state: State) -> dict:
        """Pause for the employee's answer. `enrollment_confirmed` is set here, from the answer, never by the model."""
        course_id = state["pending_course_id"]
        title = self.catalog.courses[course_id].title
        answer = interrupt({"course_id": course_id, "title": title, "question": render_enroll_question(course_id, title)})
        if answer_is_yes(answer, course_id):
            return {"enrollment_confirmed": True, "confirmed_course_id": course_id}
        return {"enrollment_confirmed": False, "confirmed_course_id": None, "pending_course_id": None,
                "reply": prompts.NOT_ENROLLED, "outcome": "enroll_declined"}

    def enroll(self, state: State) -> dict:
        """The only code that writes an enrollment (F13). Needs a confirmation for this same course."""
        course_id = state.get("pending_course_id")
        if not (state.get("enrollment_confirmed") and course_id and state.get("confirmed_course_id") == course_id):
            return {"reply": prompts.NOT_ENROLLED, "outcome": "enroll_declined"}
        added = self.store.add(state["employee_id"], course_id)
        title = self.catalog.courses[course_id].title
        return {"reply": render_enrolled(course_id, title, added), "outcome": "enrolled",
                "pending_course_id": None, "enrollment_confirmed": False, "confirmed_course_id": None}


# ---- edge decisions, kept here so they are easy to test -------------------------------------------

def after_guard(state: State) -> str:
    return "end" if state["route"] == "refuse" else "route"


def after_route(state: State) -> str:
    # FOLLOWUP shares the advise path until the follow-up node is built (phase 5).
    return {ENROLL: "enroll_agent", ADVISE: "advise_agent", FOLLOWUP: "advise_agent", OUT_OF_SCOPE: "out_of_scope"}[state["route"]]


def after_agent(state: State) -> str:
    if state["outcome"] == MODEL_ERROR:
        return "end"
    if state["pending_calls"]:
        return "run_tools"
    return "tool_fallback" if state["agent_steps"] >= MAX_AGENT_STEPS else "advise_agent"


def after_tools(state: State) -> str:
    if required_calls_done(state["called_tools"]):
        return "compose"
    return "tool_fallback" if state["agent_steps"] >= MAX_AGENT_STEPS else "advise_agent"


def after_compose(state: State) -> str:
    return "end" if state["outcome"] == MODEL_ERROR else "validate"


def after_validate(state: State) -> str:
    return {"ok": "respond", "repair": "compose"}.get(state["verdict"], "end")


def after_enroll_agent(state: State) -> str:
    return "confirm" if state["outcome"] == "enroll_proposed" else "end"


def after_confirm(state: State) -> str:
    return "enroll" if state.get("enrollment_confirmed") else "end"
