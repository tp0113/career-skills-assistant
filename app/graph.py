"""Wire the nodes into the LangGraph and wrap it in a small `Assistant` the CLI and API call.

Flow (docs/ARCHITECTURE.md): guard -> route -> advise_agent <-> run_tools -> compose -> validate
-> respond, followup (no model), or enroll_agent -> confirm (interrupt) -> enroll. The thread id is
"{employee_id}:{conversation_id}", so two employees never share state (F19).
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from app import nodes as n
from app import prompts
from app.config import Settings
from app.data import Catalog
from app.enrollments import EnrollmentStore
from app.llm import LLM
from app.state import State


def build_graph(catalog: Catalog, llm: LLM, store: EnrollmentStore, defense: bool, checkpointer=None):
    nodes = n.Nodes(catalog, llm, store, defense)
    graph = StateGraph(State)
    for name in ("guard", "route", "out_of_scope", "followup", "tool_fallback", "advise_agent", "run_tools", "compose",
                 "validate", "respond", "enroll_agent", "confirm", "enroll"):
        graph.add_node(name, getattr(nodes, name))
    graph.set_entry_point("guard")
    end = {"end": END}
    graph.add_conditional_edges("guard", n.after_guard, {"route": "route", **end})
    graph.add_conditional_edges("route", n.after_route, {
        "enroll_agent": "enroll_agent", "advise_agent": "advise_agent", "followup": "followup",
        "out_of_scope": "out_of_scope"})
    graph.add_conditional_edges("advise_agent", n.after_agent, {
        "run_tools": "run_tools", "advise_agent": "advise_agent", "tool_fallback": "tool_fallback", **end})
    graph.add_conditional_edges("run_tools", n.after_tools, {
        "compose": "compose", "advise_agent": "advise_agent", "tool_fallback": "tool_fallback"})
    graph.add_conditional_edges("compose", n.after_compose, {"validate": "validate", **end})
    graph.add_conditional_edges("validate", n.after_validate, {"respond": "respond", "compose": "compose", **end})
    graph.add_conditional_edges("enroll_agent", n.after_enroll_agent, {"confirm": "confirm", **end})
    graph.add_conditional_edges("confirm", n.after_confirm, {"enroll": "enroll", **end})
    for name in ("out_of_scope", "followup", "tool_fallback", "respond", "enroll"):
        graph.add_edge(name, END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def _interrupt_value(snapshot) -> dict | None:
    """The confirm question, if the thread waits at it. A step left over from a crash is not a pause."""
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None


@dataclass
class TurnResult:
    """What a caller (CLI, API, evals) needs from one turn."""

    reply: str
    route: str = ""
    outcome: str = ""
    recommendation: dict | None = None
    pending_enrollment: dict | None = None
    events: list[dict] = field(default_factory=list)
    flagged: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    repair_attempts: int = 0
    validation_errors: list[str] = field(default_factory=list)
    called_tools: list[str] = field(default_factory=list)


class Assistant:
    def __init__(self, settings: Settings, catalog: Catalog, llm: LLM, store: EnrollmentStore | None = None) -> None:
        self.catalog = catalog
        self.store = store or EnrollmentStore(settings.enrollments_path)
        self.graph = build_graph(catalog, llm, self.store, settings.injection_defense)

    def _config(self, employee_id: str, conversation_id: str) -> dict:
        if employee_id not in self.catalog.employees:
            raise ValueError(f"unknown employee '{employee_id}'")
        return {"configurable": {"thread_id": f"{employee_id}:{conversation_id}"}}

    def _is_paused(self, config: dict) -> bool:
        return _interrupt_value(self.graph.get_state(config)) is not None

    def _run(self, graph_input, config: dict, on_call: Callable[[str], None] | None) -> None:
        """Run the graph. `on_call(tool_name)` fires when the model has chosen a tool, before it runs (for the UI status)."""
        for update in self.graph.stream(graph_input, config, stream_mode="updates"):
            if on_call is None:
                continue
            for node_update in update.values():
                # The pause at the confirm step arrives as a tuple of interrupts, not a dict of fields.
                updates = node_update if isinstance(node_update, dict) else {}
                for call in updates.get("pending_calls") or []:
                    on_call(call["name"])

    def ask(self, employee_id: str, conversation_id: str, message: str,
            on_call: Callable[[str], None] | None = None) -> TurnResult:
        """A new message. If the thread is waiting at the confirm step, the text is the answer to it."""
        if not isinstance(message, str):
            raise TypeError("message must be text; buttons use confirm()")
        config = self._config(employee_id, conversation_id)
        if self._is_paused(config):
            self._run(Command(resume=message), config, on_call)
        else:
            self._run({"employee_id": employee_id, "user_message": message}, config, on_call)
        return self._result(config)

    def confirm(self, employee_id: str, conversation_id: str, confirm: bool, course_id: str) -> TurnResult:
        """The UI's Confirm/Decline buttons, for the course they were shown for. With nothing pending this does nothing."""
        config = self._config(employee_id, conversation_id)
        if not self._is_paused(config):
            return TurnResult(reply=prompts.NOTHING_PENDING, outcome="nothing_pending")
        self._run(Command(resume={"confirm": confirm, "course_id": course_id}), config, None)
        return self._result(config)

    def _result(self, config: dict) -> TurnResult:
        snapshot = self.graph.get_state(config)
        values = snapshot.values
        pending = _interrupt_value(snapshot)
        outcome = "enroll_pending" if pending else values.get("outcome", "")
        return TurnResult(
            reply=pending["question"] if pending else values.get("reply", ""),
            route=values.get("route", ""),
            outcome=outcome,
            # The thread remembers the last recommendation; a result shows it only if this turn validated it.
            recommendation=values.get("recommendation") if outcome == "ok" else None,
            pending_enrollment=pending,
            events=values.get("events", []),
            flagged=values.get("flagged", []),
            usage=values.get("usage", {}),
            repair_attempts=values.get("repair_attempts", 0),
            validation_errors=values.get("validation_errors", []),
            called_tools=values.get("called_tools", []),
        )

    def state_of(self, employee_id: str, conversation_id: str) -> dict:
        """The saved state of one thread. Used by tests to prove threads share nothing."""
        return dict(self.graph.get_state(self._config(employee_id, conversation_id)).values)
