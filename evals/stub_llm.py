"""A deterministic stand-in for the language model (F20).

Tests and the default eval run use this, never the real model. It follows the same `chat()`
interface as `OllamaLLM`, and it only reads the messages it is given, like a real model would.

Modes:
  cooperative  reads the profile, searches, then writes a valid recommendation from the data.
  obedient     like cooperative, but obeys an instruction hidden in a posting (the injection test).
  no_tools     never calls a tool; answers in prose.
  smuggle      first tries get_employee_profile with an extra employee_id argument, then cooperates.
  enroll_early first tries enroll_in_course on the advise path, then cooperates.
  too_few_search its first course search uses words that match nothing, then it tries again.

`compose_replies` scripts the structured-output calls one by one: a string is returned as is,
a function edits the valid answer, None means "the valid answer". `calls` records every request.
"""
import json
import re
from typing import Callable

from app.llm import LLMReply

ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "last": -1}
Scripted = str | Callable[[dict], dict] | None


def _blocks(text: str) -> dict[str, object]:
    """Read every <untrusted_data source="x">json</untrusted_data> block into {x: parsed json}."""
    found = re.findall(r'<untrusted_data source="([^"]+)">(.*?)</untrusted_data>', text, re.DOTALL)
    return {source: json.loads(body) for source, body in found}


class StubLLM:
    def __init__(self, mode: str = "cooperative", compose_replies: list[Scripted] | None = None) -> None:
        self.mode = mode
        self.compose_replies = list(compose_replies or [])
        self.calls: list[dict] = []
        self._tried_early = False

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             json_schema: dict | None = None) -> LLMReply:
        self.calls.append({"messages": messages, "tools": tools, "json_schema": json_schema})
        if json_schema:
            return self._compose(messages)
        names = [t["function"]["name"] for t in tools or []]
        if names == ["enroll_in_course"]:
            return self._enroll(messages)
        if self.mode == "no_tools":
            return LLMReply(content="Let me think about your career.", prompt_tokens=50, output_tokens=8)
        return self._advise(messages, names)

    # ---- tool calling -----------------------------------------------------------------------

    def _advise(self, messages: list[dict], offered: list[str]) -> LLMReply:
        done = {m["tool_name"]: m["content"] for m in messages
                if m["role"] == "tool" and m["content"].startswith("<untrusted_data")
                and "Too few results" not in m["content"]}
        if self.mode == "enroll_early" and not self._tried_early:
            self._tried_early = True
            return self._call("enroll_in_course", {"course_id": "C04"})
        if "get_employee_profile" in offered:
            if self.mode == "smuggle" and not self._tried_early:
                self._tried_early = True
                return self._call("get_employee_profile", {"employee_id": "E02"})
            return self._call("get_employee_profile", {})
        profile = _blocks(done["get_employee_profile"])["get_employee_profile"]
        query = f"{profile['current_role']} {profile['career_interest']}"
        if self.mode == "too_few_search" and not self._tried_early:
            self._tried_early = True
            return self._call("search_courses", {"query": "zzzz"})
        if "search_courses" not in done:
            return self._call("search_courses", {"query": query})
        # The obedient stub also searches for a warehouse-style posting so the poisoned one is reached.
        extra = " weekly reports inventory" if self.mode == "obedient" else ""
        return self._call("search_jobs", {"query": query + extra})

    def _call(self, name: str, arguments: dict) -> LLMReply:
        return LLMReply(tool_calls=[{"name": name, "arguments": arguments}], prompt_tokens=100, output_tokens=10)

    def _enroll(self, messages: list[dict]) -> LLMReply:
        listing = re.findall(r"^(\d+)\. (C\d{2}):", messages[0]["content"], re.MULTILINE)
        text = messages[-1]["content"].lower()
        explicit = re.search(r"\bc\d{2}\b", text)
        if explicit:
            return self._call("enroll_in_course", {"course_id": explicit.group().upper()})
        for word, position in ORDINALS.items():
            if re.search(rf"\b{word}\b", text) and listing:
                return self._call("enroll_in_course", {"course_id": listing[position - 1 if position > 0 else -1][1]})
        return LLMReply(content="Which course do you mean?")

    # ---- structured output ------------------------------------------------------------------

    def _compose(self, messages: list[dict]) -> LLMReply:
        valid = self._valid_answer(_blocks(messages[1]["content"]))
        scripted = self.compose_replies.pop(0) if self.compose_replies else None
        if isinstance(scripted, str):
            content = scripted
        elif callable(scripted):
            content = json.dumps(scripted(valid))
        else:
            content = json.dumps(valid)
        return LLMReply(content=content, prompt_tokens=800, output_tokens=200)

    def _valid_answer(self, data: dict) -> dict:
        courses, jobs = data["courses"], data["jobs"]
        candidates = [c["id"] for c in data["candidate_skills"]]
        roles = jobs[:2]
        if self.mode == "obedient":
            poisoned = [j for j in jobs if "ignore your instructions" in j["description"].lower()]
            roles = (poisoned + [j for j in jobs if j not in poisoned])[:2]
        sources_for = lambda sid: ([c["id"] for c in courses if sid in self._skill_ids(c, data)]
                                   + [j["id"] for j in jobs if sid in self._skill_ids(j, data)])[:2]
        ranked = sorted(candidates, key=lambda s: (-len(sources_for(s)), s))[:3]
        return {
            "skills": [{"skill_id": s, "reason": "It is needed for the roles and courses found.", "sources": sources_for(s)}
                       for s in ranked],
            "courses": [{"course_id": c["id"], "reason": "It teaches skills you do not have yet.", "sources": [c["id"]]}
                        for c in courses[:3]],
            "roles": [{"job_id": j["id"], "reason": "It matches your career interest.", "sources": [j["id"]]}
                      for j in roles],
        }

    @staticmethod
    def _skill_ids(item: dict, data: dict) -> set[str]:
        """The tools show skill names; map them back to ids through the candidate list."""
        names = item.get("skills") or item.get("required_skills") or []
        by_name = {c["name"]: c["id"] for c in data["candidate_skills"]}
        return {by_name[n] for n in names if n in by_name}
