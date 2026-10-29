import pytest

from app.config import load_settings
from app.data import load_catalog
from app.enrollments import EnrollmentStore
from app.graph import Assistant
from app.profile import render_profile
from app.router import ADVISE, PROFILE, route_message
from evals.stub_llm import StubLLM

SETTINGS = load_settings()
CATALOG = load_catalog(SETTINGS.data_dir)
MARCUS = ("Marcus", "Marcus Okafor")


@pytest.mark.parametrize("message", [
    "list my skills", "What are my courses?", "what skills do I have", "What courses have I completed?",
    "Show my profile please", "what are my skills and courses", "what's my skills",
])
def test_plain_questions_about_own_data_are_profile(message):
    assert route_message(message) == PROFILE


@pytest.mark.parametrize("message", [
    "What skills should I develop for my next career opportunity?",
    "what courses fit my skills",
    "Which of my skills is best for a new role?",
    "What is the weather on the last day of my course?",
    "Recommend a course for my skills",
])
def test_advice_and_unrelated_questions_stay_off_the_profile_route(message):
    assert route_message(message) == ADVISE


def test_own_name_possessive_counts_as_my():
    assert route_message("What are Marcus's skills?", None, MARCUS) == PROFILE
    assert route_message("What are Marcus's skills?") != PROFILE  # without the signed-in name it is not first person


def test_skills_question_lists_only_skills():
    reply = render_profile("list my skills", "E03", CATALOG, [])
    assert "Your skills" in reply and "Courses you have completed" not in reply


def test_courses_question_lists_completed_and_enrolled_courses():
    reply = render_profile("what are my courses?", "E01", CATALOG, ["C03"])
    assert "Courses you have completed" in reply and CATALOG.courses["C01"].title in reply
    assert "Courses you are enrolled in\n- " + CATALOG.courses["C03"].title in reply and "Your skills" not in reply


def test_profile_turn_makes_no_model_call_and_uses_the_signed_in_employee(tmp_path):
    assistant = Assistant(SETTINGS, CATALOG, StubLLM(), EnrollmentStore(tmp_path / "e.json"))
    result = assistant.ask("E02", "c1", "What are Marcus's skills?")
    assert result.route == "profile" and result.outcome == "profile" and result.usage["model_calls"] == 0
    assert CATALOG.employees["E02"].name in result.reply and CATALOG.employees["E01"].name not in result.reply


def test_asking_about_a_colleague_is_still_refused(tmp_path):
    assistant = Assistant(SETTINGS, CATALOG, StubLLM(), EnrollmentStore(tmp_path / "e.json"))
    result = assistant.ask("E01", "c1", "What are Marcus's skills?")
    assert result.route == "refuse" and result.usage["model_calls"] == 0
