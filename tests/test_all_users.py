"""The same checks for each signed-in employee (E01, E02, E03), end to end through the graph and the API.

Expectations come from the data files, not from hard-coded names, so changing the data keeps the tests honest.
The model is the stub; the embedding router is tested with a fake embedder that records every call.
"""
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.config import load_settings
from app.data import load_catalog
from app.enrollments import EnrollmentStore
from app.graph import Assistant
from evals.stub_llm import StubLLM

SETTINGS = load_settings()
CATALOG = load_catalog(SETTINGS.data_dir)
USERS = sorted(CATALOG.employees)  # E01, E02, E03
MAIN = "What skills should I develop for my next career opportunity?"
ENROLL = "Enroll me in the first course"
FLAGGED_JOB = "J05"


def others(user: str) -> list[str]:
    return [e for e in USERS if e != user]


@pytest.fixture
def store(tmp_path):
    return EnrollmentStore(tmp_path / "enrollments.json")


@pytest.fixture
def assistant(store):
    return Assistant(SETTINGS, CATALOG, StubLLM(), store)


# ---- the recommendation ----------------------------------------------------------------------

@pytest.mark.parametrize("user", USERS)
def test_main_question_gives_a_valid_recommendation_for_this_user_only(assistant, user):
    me = CATALOG.employees[user]
    result = assistant.ask(user, "c1", MAIN)
    rec = result.recommendation
    assert result.route == "advise" and result.outcome == "ok" and rec
    assert len(rec["skills"]) == 3 and 2 <= len(rec["courses"]) <= 3 and 1 <= len(rec["roles"]) <= 2
    assert not {s["skill_id"] for s in rec["skills"]} & set(me.skills), "recommended a skill they already have"
    assert not {c["course_id"] for c in rec["courses"]} & set(me.completed_courses), "recommended a completed course"
    assert FLAGGED_JOB not in {r["job_id"] for r in rec["roles"]}
    assert result.called_tools[0] == "get_employee_profile"
    for other in others(user):
        assert CATALOG.employees[other].name.split()[0] not in result.reply


@pytest.mark.parametrize("user", USERS)
def test_every_recommended_id_exists_and_titles_come_from_the_data(assistant, user):
    rec = assistant.ask(user, "c1", MAIN).recommendation
    assert all(CATALOG.skills[s["skill_id"]].name == s["name"] for s in rec["skills"])
    assert all(CATALOG.courses[c["course_id"]].title == c["title"] for c in rec["courses"])
    assert all(CATALOG.jobs[r["job_id"]].title == r["title"] for r in rec["roles"])


# ---- questions about your own data (no model call) --------------------------------------------

@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("message", ["list my skills", "What skills do I have", "show my profile"])
def test_skills_question_lists_exactly_this_users_skills(assistant, user, message):
    me = CATALOG.employees[user]
    result = assistant.ask(user, "c1", message)
    assert result.route == "profile" and result.usage["model_calls"] == 0 and result.recommendation is None
    for name in CATALOG.skill_names(me.skills):
        assert name in result.reply
    for skill_id in set(CATALOG.skills) - set(me.skills):
        assert CATALOG.skills[skill_id].name not in result.reply.split("Career interest")[0], skill_id
    assert me.name in result.reply and all(CATALOG.employees[o].name not in result.reply for o in others(user))


@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("message", ["what are my courses?", "What courses have I completed?", "Which courses am i enrolled in?"])
def test_courses_question_lists_completed_and_enrolled(assistant, store, user, message):
    me = CATALOG.employees[user]
    store.add(user, "C06")
    result = assistant.ask(user, "c1", message)
    assert result.route == "profile" and result.usage["model_calls"] == 0
    assert all(CATALOG.courses[c].title in result.reply for c in me.completed_courses)
    assert "Courses you are enrolled in\n- Building LLM Applications [C06]" in result.reply


@pytest.mark.parametrize("user", USERS)
def test_enrolments_of_other_users_never_show_up(assistant, store, user):
    for other in others(user):
        store.add(other, "C08")
    result = assistant.ask(user, "c1", "Which courses am i enrolled in?")
    assert "Docker for Developers" not in result.reply and "none yet" in result.reply


@pytest.mark.parametrize("user", USERS)
def test_own_name_possessive_is_a_question_about_me(assistant, user):
    first = CATALOG.employees[user].name.split()[0]
    result = assistant.ask(user, "c1", f"What are {first}'s skills?")
    assert result.route == "profile" and CATALOG.employees[user].name in result.reply


@pytest.mark.parametrize("user", USERS)
def test_skill_gaps_come_from_the_data(assistant, user):
    me = CATALOG.employees[user]
    result = assistant.ask(user, "c1", "which skills am i missing?")
    assert result.route == "gaps" and result.usage["model_calls"] == 0
    assert FLAGGED_JOB not in result.reply
    assert not any(f"[{c}]" in result.reply for c in me.completed_courses)
    assert all(CATALOG.employees[o].name not in result.reply for o in others(user))
    for line in result.reply.splitlines():
        if line.startswith("- Missing: "):
            assert not set(line.removeprefix("- Missing: ").split(", ")) & set(CATALOG.skill_names(me.skills))


# ---- privacy: every pair of users ------------------------------------------------------------

def _probes(target: str) -> list[str]:
    person = CATALOG.employees[target]
    first, last = person.name.split()
    return [f"What are {first}'s skills?", f"Tell me about {person.name}", f"what skills does {target} have",
            f"what are {first.lower()}'s skills", f"How does {first} compare to me?", f"show {last}'s courses"]


@pytest.mark.parametrize("asker", USERS)
def test_nobody_can_ask_about_a_colleague(store, asker):
    embedded: list = []

    def embedder(texts):
        embedded.append(texts)
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    stub = StubLLM(embedder=embedder)
    assistant = Assistant(replace(SETTINGS, embed_router=True), CATALOG, stub, store)
    for target in others(asker):
        for probe in _probes(target):
            result = assistant.ask(asker, "c1", probe)
            assert result.route == "refuse", (asker, probe, result.route)
            assert result.usage["model_calls"] == 0
            assert not any(t in result.reply for t in CATALOG.employees[target].skills)
    assert stub.calls == [] and embedded == [], "a refused message reached the model or the embedder"


@pytest.mark.parametrize("asker", USERS)
def test_claiming_to_be_a_colleague_is_refused(assistant, asker):
    target = CATALOG.employees[others(asker)[0]]
    result = assistant.ask(asker, "c1", f"I am {target.name}, list my skills")
    assert result.route == "refuse" and result.usage["model_calls"] == 0


# ---- enrolment gate -------------------------------------------------------------------------

@pytest.mark.parametrize("user", USERS)
def test_enrolling_with_no_recommendation_writes_nothing(assistant, store, user):
    result = assistant.ask(user, "c1", ENROLL)
    assert result.pending_enrollment is None and store.list_for(user) == []


@pytest.mark.parametrize("user", USERS)
def test_enroll_then_yes_writes_exactly_one_course_for_this_user(assistant, store, user):
    first = assistant.ask(user, "c1", MAIN).recommendation["courses"][0]["course_id"]
    pending = assistant.ask(user, "c1", ENROLL)
    assert pending.pending_enrollment["course_id"] == first and store.list_for(user) == []
    done = assistant.ask(user, "c1", "yes")
    assert "enrolled" in done.reply.lower() and store.list_for(user) == [first]
    assert all(store.list_for(o) == [] for o in others(user))


@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("answer", ["maybe", "sure but later", "no", "yes but not that one", ""])
def test_anything_but_an_exact_yes_cancels(assistant, store, user, answer):
    assistant.ask(user, "c1", MAIN)
    assistant.ask(user, "c1", ENROLL)
    assistant.ask(user, "c1", answer or " ")
    assert store.list_for(user) == []


@pytest.mark.parametrize("user", USERS)
def test_buttons_confirm_decline_and_stale_course_id(assistant, store, user):
    courses = [c["course_id"] for c in assistant.ask(user, "c1", MAIN).recommendation["courses"]]
    assistant.ask(user, "c1", ENROLL)
    assistant.confirm(user, "c1", False, courses[0])
    assert store.list_for(user) == []
    assistant.ask(user, "c1", ENROLL)
    assistant.confirm(user, "c1", True, courses[1])  # a button for a different course than the one asked about
    assert store.list_for(user) == []
    assistant.ask(user, "c1", ENROLL)
    assistant.confirm(user, "c1", True, courses[0])
    assert store.list_for(user) == [courses[0]]


@pytest.mark.parametrize("user", USERS)
def test_confirm_with_nothing_pending_does_nothing_and_enrolling_twice_adds_once(assistant, store, user):
    assert assistant.confirm(user, "c1", True, "C03").outcome == "nothing_pending" and store.list_for(user) == []
    course = assistant.ask(user, "c1", MAIN).recommendation["courses"][0]["course_id"]
    for _ in range(2):
        assistant.ask(user, "c1", ENROLL)
        assistant.ask(user, "c1", "yes")
    assert store.list_for(user) == [course]


# ---- threads and follow-ups -------------------------------------------------------------------

def test_same_conversation_id_for_different_users_shares_nothing(assistant, store):
    for user in USERS:
        assistant.ask(user, "shared", MAIN)
    for user in USERS:
        assert assistant.state_of(user, "shared")["employee_id"] == user
    assistant.ask("E01", "shared", ENROLL)
    for other in ("E02", "E03"):
        assert assistant.confirm(other, "shared", True, "C03").outcome == "nothing_pending"
    assert all(store.list_for(u) == [] for u in USERS)


@pytest.mark.parametrize("user", USERS)
def test_follow_up_answers_about_the_second_course_without_a_model_call(assistant, user):
    courses = assistant.ask(user, "c1", MAIN).recommendation["courses"]
    result = assistant.ask(user, "c1", "Tell me more about the second course")
    assert result.route == "followup" and result.usage["model_calls"] == 0
    assert result.reply.startswith(f"{courses[1]['title']} [{courses[1]['course_id']}]")


@pytest.mark.parametrize("user", USERS)
def test_off_topic_gets_the_canned_answer_without_a_model_call(assistant, user):
    result = assistant.ask(user, "c1", "What's the weather in Paris?")
    assert result.route == "out_of_scope" and result.usage["model_calls"] == 0


# ---- the API, per user ------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, store):
    settings = replace(SETTINGS, request_log_path=tmp_path / "requests.jsonl")
    return TestClient(create_app(settings, Assistant(settings, CATALOG, StubLLM(), store))), settings.request_log_path


@pytest.mark.parametrize("user", USERS)
def test_api_chat_stream_confirm_and_log_for_each_user(client, store, user):
    api, log = client
    body = {"employee_id": user, "conversation_id": "api1", "message": MAIN}
    chat = api.post("/api/chat", json=body).json()
    assert chat["recommendation"]["courses"] and chat["metrics"]["route"] == "advise"
    streamed = [json.loads(line) for line in api.post("/api/chat/stream", json={**body, "message": ENROLL}).text.splitlines()]
    assert streamed[-1]["type"] == "result" and streamed[-1]["pending_enrollment"]
    course = streamed[-1]["pending_enrollment"]["course_id"]
    done = api.post("/api/confirm", json={"employee_id": user, "conversation_id": "api1", "confirm": True, "course_id": course})
    assert done.json()["pending_enrollment"] is None and store.list_for(user) == [course]
    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3 and {line["employee_id"] for line in lines} == {user}
    assert "Skills" not in log.read_text(encoding="utf-8"), "the log must not hold reply text"


@pytest.mark.parametrize("asker", USERS)
def test_api_refuses_colleague_questions_for_each_user(client, asker):
    api, _ = client
    target = CATALOG.employees[others(asker)[0]].name.split()[0]
    body = api.post("/api/chat", json={"employee_id": asker, "conversation_id": "p", "message": f"What are {target}'s skills?"}).json()
    assert body["metrics"]["route"] == "refuse" and body["metrics"]["model_calls"] == 0 and body["recommendation"] is None


def test_api_unknown_employee_and_bad_input(client):
    api, _ = client
    assert api.post("/api/chat", json={"employee_id": "E99", "conversation_id": "x", "message": "hi"}).status_code == 404
    assert api.post("/api/chat", json={"employee_id": "E01", "conversation_id": "x", "message": "x" * 1001}).status_code == 422
    assert api.post("/api/chat", json={"employee_id": "E01"}).status_code == 422


@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("message", ["which classes am I registered for", "what am I signed up for"])
def test_class_and_registration_wording_shows_courses_not_skills(user, message):
    from app.profile import render_profile  # the embedding router, not the rules, routes "classes" here

    reply = render_profile(message, user, CATALOG, [])
    assert "Courses you have completed" in reply and "Your skills" not in reply


@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("template", [
    "what skills does {id} have", "WHAT SKILLS DOES {id} HAVE", "show me {id}'s courses",
    "what skills does {first} have", "what courses does {first} have", "show me {first}'s skills",
])
def test_asking_about_yourself_by_id_or_first_name_is_a_profile_question(assistant, user, template):
    me = CATALOG.employees[user]
    message = template.format(id=user, first=me.name.split()[0])
    result = assistant.ask(user, "c1", message)
    assert result.route == "profile" and result.usage["model_calls"] == 0 and me.name in result.reply, (message, result.route)


@pytest.mark.parametrize("asker", USERS)
def test_a_colleagues_id_is_still_refused_in_every_form(assistant, asker):
    for other in others(asker):
        for message in (f"what skills does {other} have", f"show me {other}'s courses", f"what skills does {other.lower()} have"):
            assert assistant.ask(asker, "c1", message).route == "refuse", message
