import pytest

from app import prompts
from app.config import load_settings
from app.data import load_catalog
from app.enrollments import EnrollmentStore
from app.gaps import render_gaps
from app.graph import Assistant
from app.router import ADVISE, GAPS, PROFILE, route_message
from evals.stub_llm import StubLLM

SETTINGS = load_settings()
CATALOG = load_catalog(SETTINGS.data_dir)


@pytest.mark.parametrize("message", [
    "which skills am i missing?", "What am I missing?", "my skill gaps", "what skills do I lack",
])
def test_gap_questions_go_to_the_gaps_route(message):
    assert route_message(message) == GAPS


@pytest.mark.parametrize("message", [
    "Which courses am i enrolled in?", "what am I enrolled in", "List my enrollments", "what do I know",
    "What have I completed",
])
def test_more_own_data_phrasings_are_profile(message):
    assert route_message(message) == PROFILE


def test_advice_questions_are_still_advice():
    assert route_message("What skills should I develop for my next career opportunity?") == ADVISE


def test_gaps_compare_the_closest_role_with_the_employees_own_skills():
    reply = render_gaps("E01", CATALOG)
    assert "Machine Learning Engineer [J01]" in reply
    assert "You have: Statistics" in reply and "Missing: Python, Machine learning, Docker and containers" in reply


def test_gaps_never_list_the_flagged_posting():
    for employee in CATALOG.employees:
        assert "J05" not in render_gaps(employee, CATALOG)


def test_gaps_do_not_suggest_completed_courses():
    for employee_id, employee in CATALOG.employees.items():
        reply = render_gaps(employee_id, CATALOG)
        assert not any(f"[{course_id}]" in reply for course_id in employee.completed_courses)


def test_gaps_turn_makes_no_model_call_and_only_names_the_signed_in_employees_data(tmp_path):
    assistant = Assistant(SETTINGS, CATALOG, StubLLM(), EnrollmentStore(tmp_path / "e.json"))
    result = assistant.ask("E03", "c1", "which skills am i missing?")
    assert result.route == "gaps" and result.outcome == "gaps" and result.usage["model_calls"] == 0
    assert "Technical Product Manager, AI [J04]" in result.reply and "Missing: Prompt engineering" in result.reply


def test_enrolled_courses_question_lists_enrollments_not_a_recommendation(tmp_path):
    store = EnrollmentStore(tmp_path / "e.json")
    store.add("E01", "C06")
    result = Assistant(SETTINGS, CATALOG, StubLLM(), store).ask("E01", "c1", "Which courses am i enrolled in?")
    assert result.route == "profile" and result.recommendation is None and result.usage["model_calls"] == 0
    assert "Courses you are enrolled in\n- Building LLM Applications [C06]" in result.reply


def test_failure_message_points_to_questions_that_work():
    for example in ("list my skills", "which courses am I enrolled in", "which skills am I missing"):
        assert example in prompts.VALIDATION_FAILURE
        assert route_message(example) in (GAPS, PROFILE)


def test_a_flagged_posting_is_skipped_even_when_the_interest_matches_it():
    from app.gaps import _roles_for_interest

    assert "J05" in CATALOG.jobs and _roles_for_interest(CATALOG, "warehouse operations coordinator") == []
