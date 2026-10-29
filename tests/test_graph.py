import json
from dataclasses import replace

import pytest

from app import prompts
from app.config import load_settings
from app.data import load_catalog
from app.enrollments import EnrollmentStore
from app.graph import Assistant
from evals.stub_llm import StubLLM

SETTINGS = load_settings()
CATALOG = load_catalog(SETTINGS.data_dir)
MAIN = "What skills should I develop for my next career opportunity?"
ENROLL_FIRST = "Enroll me in the first course"


@pytest.fixture
def store(tmp_path):
    return EnrollmentStore(tmp_path / "enrollments.json")


def make(store, **stub_args) -> tuple[Assistant, StubLLM]:
    stub = StubLLM(**stub_args)
    return Assistant(SETTINGS, CATALOG, stub, store), stub


def recommended(assistant, employee="E01", conv="c1"):
    return assistant.ask(employee, conv, MAIN).recommendation["courses"]


# ---- main path ------------------------------------------------------------------------------

@pytest.mark.parametrize("employee", ["E01", "E02", "E03"])
def test_main_path_gives_a_valid_recommendation(store, employee):
    assistant, _ = make(store)
    result = assistant.ask(employee, "c1", MAIN)
    rec = result.recommendation
    assert result.route == "advise" and result.outcome == "ok"
    assert len(rec["skills"]) == 3 and 2 <= len(rec["courses"]) <= 3 and 1 <= len(rec["roles"]) <= 2
    assert result.called_tools == ["get_employee_profile", "search_courses", "search_jobs"]
    assert rec["courses"][0]["title"] in result.reply
    assert result.usage["model_calls"] == 4 and result.usage["compose_prompt_tokens"] > 0


def test_tools_are_offered_in_stages(store):
    assistant, stub = make(store)
    assistant.ask("E01", "c1", MAIN)
    offered = [[t["function"]["name"] for t in c["tools"]] for c in stub.calls if c["tools"]]
    assert offered == [["get_employee_profile"], ["search_courses", "search_jobs"], ["search_courses", "search_jobs"]]


def test_compose_call_sends_the_json_schema_and_no_tools(store):
    assistant, stub = make(store)
    assistant.ask("E01", "c1", MAIN)
    compose = stub.calls[-1]
    assert compose["tools"] is None
    assert set(compose["json_schema"]["properties"]) == {"skills", "courses", "roles"}


# ---- guard, router, fallback ----------------------------------------------------------------

def test_refused_message_never_reaches_the_model(store):
    assistant, stub = make(store)
    result = assistant.ask("E01", "c1", "What are Marcus's skills?")
    assert result.outcome == "refused" and result.reply == prompts.REFUSAL
    assert stub.calls == []
    assert "Okafor" not in result.reply and "Frontend" not in result.reply


def test_out_of_scope_is_a_canned_answer_with_no_model_call(store):
    assistant, stub = make(store)
    result = assistant.ask("E02", "c1", "What's the weather in Paris?")
    assert result.outcome == "out_of_scope" and result.reply == prompts.OUT_OF_SCOPE and stub.calls == []


def test_a_model_that_never_calls_tools_hits_the_fallback_after_6_steps(store):
    assistant, stub = make(store, mode="no_tools")
    result = assistant.ask("E01", "c1", MAIN)
    assert result.outcome == "tool_fallback" and result.reply == prompts.TOOL_FALLBACK
    assert result.recommendation is None
    assert len(stub.calls) == 6
    assert any(m.get("content") == prompts.TOOL_REMINDER for m in stub.calls[1]["messages"])


def test_smuggled_employee_id_gets_an_error_and_no_other_data(store):
    assistant, _ = make(store, mode="smuggle")
    result = assistant.ask("E01", "c1", MAIN)
    first = result.events[0]
    assert first["name"] == "get_employee_profile" and not first["ok"] and "employee_id" in first["error"]
    assert result.outcome == "ok"  # the model recovered after the error message
    dump = json.dumps(assistant.state_of("E01", "c1"))
    # The rejected attempt itself is logged (it contains the text "E02"), but none of E02's data is.
    for secret in ("Marcus", "Okafor", "Frontend Developer", "Elena", "Petrova", "Build AI-powered"):
        assert secret not in dump
    assert assistant.state_of("E01", "c1")["profile"]["name"] == "Priya Shah"


def test_enroll_called_on_the_advise_route_writes_nothing(store):
    assistant, _ = make(store, mode="enroll_early")
    result = assistant.ask("E01", "c1", MAIN)
    assert result.events[0]["name"] == "enroll_in_course" and not result.events[0]["ok"]
    assert "not available" in result.events[0]["error"]
    assert store.list_for("E01") == [] and result.pending_enrollment is None


# ---- repair ---------------------------------------------------------------------------------

def test_malformed_json_is_repaired_once(store):
    assistant, stub = make(store, compose_replies=["this is not json", None])
    result = assistant.ask("E01", "c1", MAIN)
    assert result.outcome == "ok" and result.repair_attempts == 1
    repair = stub.calls[-1]["messages"][-1]
    assert repair["role"] == "user" and "not valid JSON" in repair["content"]


def test_completed_course_is_rejected_then_repaired(store):
    def add_completed(valid: dict) -> dict:
        valid["courses"][0] = {"course_id": "C07", "reason": "x", "sources": ["C06"]}
        return valid

    assistant, stub = make(store, compose_replies=[add_completed, None])
    result = assistant.ask("E02", "c1", MAIN)
    assert result.repair_attempts == 1 and result.outcome == "ok"
    assert "Course C07: the employee already completed" in stub.calls[-1]["messages"][-1]["content"]
    assert "C07" not in [c["course_id"] for c in result.recommendation["courses"]]


def test_three_bad_answers_end_in_a_graceful_failure(store):
    assistant, _ = make(store, compose_replies=["bad", "bad", "bad"])
    result = assistant.ask("E01", "c1", MAIN)
    assert result.outcome == "validation_failed" and result.repair_attempts == 2
    assert result.reply == prompts.VALIDATION_FAILURE and result.recommendation is None


# ---- injection ------------------------------------------------------------------------------

def test_obedient_model_cannot_recommend_the_poisoned_posting_with_defense_on(store):
    assistant, _ = make(store, mode="obedient")
    result = assistant.ask("E01", "c1", MAIN)
    assert [f["id"] for f in result.flagged] == ["J05"]
    assert "J05" not in [r["job_id"] for r in result.recommendation["roles"]]


def test_obedient_model_does_recommend_it_with_defense_off(store):
    assistant = Assistant(replace(SETTINGS, injection_defense=False), CATALOG, StubLLM(mode="obedient"), store)
    result = assistant.ask("E01", "c1", MAIN)
    assert result.flagged == []
    assert result.recommendation["roles"][0]["job_id"] == "J05"


# ---- enrollment gate ------------------------------------------------------------------------

def test_enroll_pauses_for_confirmation_and_writes_nothing(store):
    assistant, _ = make(store)
    courses = recommended(assistant)
    result = assistant.ask("E01", "c1", ENROLL_FIRST)
    assert result.outcome == "enroll_pending"
    assert result.pending_enrollment["course_id"] == courses[0]["course_id"]
    assert 'Reply "yes"' in result.reply and store.list_for("E01") == []


@pytest.mark.parametrize("answer", ["maybe", "sure but later", "no", "yes but later"])
def test_a_vague_reply_cancels_and_writes_nothing(store, answer):
    assistant, _ = make(store)
    recommended(assistant)
    assistant.ask("E01", "c1", ENROLL_FIRST)
    result = assistant.ask("E01", "c1", answer)
    assert result.outcome == "enroll_declined" and result.reply == prompts.NOT_ENROLLED
    assert store.list_for("E01") == [] and result.pending_enrollment is None


def test_decline_button_writes_nothing(store):
    assistant, _ = make(store)
    recommended(assistant)
    assistant.ask("E01", "c1", ENROLL_FIRST)
    assert assistant.confirm("E01", "c1", False).outcome == "enroll_declined"
    assert store.list_for("E01") == []


def test_confirm_writes_exactly_one_enrollment_and_replay_changes_nothing(store):
    assistant, _ = make(store)
    first = recommended(assistant)[0]["course_id"]
    assistant.ask("E01", "c1", ENROLL_FIRST)
    done = assistant.confirm("E01", "c1", True)
    assert done.outcome == "enrolled" and store.list_for("E01") == [first]
    again = assistant.confirm("E01", "c1", True)
    assert again.outcome == "nothing_pending" and store.list_for("E01") == [first]


def test_typed_yes_also_enrolls(store):
    assistant, _ = make(store)
    first = recommended(assistant)[0]["course_id"]
    assistant.ask("E01", "c1", ENROLL_FIRST)
    assert assistant.ask("E01", "c1", "Yes, please!").outcome == "enrolled"
    assert store.list_for("E01") == [first]


def test_second_enroll_request_for_the_same_course_is_refused_politely(store):
    assistant, _ = make(store)
    recommended(assistant)
    assistant.ask("E01", "c1", ENROLL_FIRST)
    assistant.confirm("E01", "c1", True)
    result = assistant.ask("E01", "c1", ENROLL_FIRST)
    assert result.outcome == "enroll_refused" and "already enrolled" in result.reply
    assert len(store.list_for("E01")) == 1


def test_enroll_without_a_recommendation_asks_first(store):
    assistant, stub = make(store)
    result = assistant.ask("E01", "c1", ENROLL_FIRST)
    assert result.outcome == "enroll_clarify" and result.reply == prompts.NO_RECOMMENDATION
    assert stub.calls == [] and store.list_for("E01") == []


def test_completed_course_cannot_be_enrolled(store):
    assistant, _ = make(store)
    recommended(assistant)
    result = assistant.ask("E01", "c1", "Enroll me in C01")
    assert result.outcome == "enroll_refused" and "already completed" in result.reply
    assert store.list_for("E01") == []


def test_a_new_recommendation_clears_a_stale_enrollment_choice(store):
    assistant, _ = make(store)
    recommended(assistant)
    assistant.ask("E01", "c1", ENROLL_FIRST)
    assistant.confirm("E01", "c1", False)
    recommended(assistant)
    state = assistant.state_of("E01", "c1")
    assert state["pending_course_id"] is None and state["enrollment_confirmed"] is False


# ---- threads --------------------------------------------------------------------------------

def test_threads_for_two_employees_share_nothing(store):
    assistant, _ = make(store)
    assistant.ask("E01", "x", MAIN)
    assistant.ask("E02", "x", MAIN)
    one, two = assistant.state_of("E01", "x"), assistant.state_of("E02", "x")
    assert one["employee_id"] == "E01" and two["employee_id"] == "E02"
    assert one["profile"]["name"] == "Priya Shah" and two["profile"]["name"] == "Marcus Okafor"
    assert one["recommendation"] != two["recommendation"]
    assert "Marcus" not in json.dumps(one) and "Priya" not in json.dumps(two)


def test_a_pending_enrollment_in_one_thread_does_not_leak_to_another(store):
    assistant, _ = make(store)
    recommended(assistant, "E01", "x")
    assistant.ask("E01", "x", ENROLL_FIRST)
    result = assistant.ask("E02", "x", ENROLL_FIRST)
    assert result.outcome == "enroll_clarify"  # E02 has no recommendation of their own yet


def test_turn_fields_reset_but_the_recommendation_survives(store):
    assistant, _ = make(store)
    recommended(assistant)
    assistant.ask("E01", "c1", "What's the weather in Paris?")
    state = assistant.state_of("E01", "c1")
    assert state["recommendation"] is not None and state["called_tools"] == [] and state["flagged"] == []


def test_unknown_employee_is_rejected(store):
    assistant, _ = make(store)
    with pytest.raises(ValueError):
        assistant.ask("E99", "c1", MAIN)
